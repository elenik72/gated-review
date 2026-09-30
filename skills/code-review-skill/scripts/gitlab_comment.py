#!/usr/bin/env python3
"""Post inline (diff-anchored) review comments to a GitLab merge request.

Why this exists: `glab api -f "position[new_line]=171" ...` does NOT work.
glab sends bracketed keys as flat form fields, GitLab never parses them into the
nested `position` object, and the API silently creates a plain MR-level comment
instead of an inline one — no error, wrong result. The only reliable way is a
JSON request body, which is what this script sends.

Usage:

    # inline comment on one changed line
    gitlab_comment.py post --mr group/project!69 \
        --file docs/rfc/foo.md --line 171 --body-file /tmp/finding1.md

    # all findings at once, straight from the gate
    finding.py render --json > /tmp/findings.json
    gitlab_comment.py post-batch --mr group/project!69 --input /tmp/findings.json

    # a question to the author — claims nothing, so it does not go through the gate
    gitlab_comment.py post --mr group/project!69 --file a.ts --line 12 --question --body-file /tmp/q.md

    # list existing [ai-review-bot] threads (the re-review work list)
    gitlab_comment.py threads --mr group/project!69 [--all]

    # reply into a thread / resolve it / delete a note
    gitlab_comment.py reply --mr group/project!69 --thread <id> --body-file /tmp/r.md
    gitlab_comment.py resolve --mr group/project!69 --thread <id>
    gitlab_comment.py delete --mr group/project!69 --note <note_id>

Every `post` verifies the result: if GitLab came back with anything other than a
`DiffNote` carrying the requested line, the script deletes the note it just made
and exits non-zero, so a review can never quietly end up with page-level comments.

`post` and `post-batch` publish only findings that passed `finding.py`: each body must be
exactly what `finding.py render` produces for a finding at that location in `.review/`
(`--dir`, default `.`). Anything else is refused before the first request, so the gate
cannot be skipped by writing a comment by hand. `reply` / `resolve` stay free.

Auth: reuses the `glab` CLI token (`glab config get token --host <host>`), or
GITLAB_TOKEN / GL_TOKEN.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import finding  # noqa: E402  — the gate: only what passed it is posted

DEFAULT_HOST = os.environ.get("GITLAB_HOST", "gitlab.task4work.info")


def token(host: str) -> str:
    for env in ("GITLAB_TOKEN", "GL_TOKEN"):
        if os.environ.get(env):
            return os.environ[env]
    out = subprocess.run(
        ["glab", "config", "get", "token", "--host", host],
        capture_output=True,
        text=True,
    )
    tok = out.stdout.strip()
    if not tok:
        sys.exit(
            f"no token for {host}: run `glab auth login --hostname {host}` "
            "or set GITLAB_TOKEN"
        )
    return tok


def api(host: str, path: str, *, method: str = "GET", payload: dict | None = None):
    url = f"https://{host}/api/v4/{path.lstrip('/')}"
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"PRIVATE-TOKEN": token(host)}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        sys.exit(f"{method} {url} -> HTTP {exc.code}: {exc.read().decode()[:500]}")


def parse_mr(ref: str) -> tuple[str, str]:
    """`group/project!69` -> (url-encoded project, iid)."""
    if "!" not in ref:
        sys.exit("--mr must look like group/project!69")
    project, iid = ref.rsplit("!", 1)
    return urllib.parse.quote(project, safe=""), iid


def diff_refs(host: str, project: str, iid: str) -> dict:
    """base/head/start SHAs of the latest version — required for an inline note."""
    versions = api(host, f"projects/{project}/merge_requests/{iid}/versions")
    if not versions:
        sys.exit("MR has no diff versions")
    v = versions[0]
    return {
        "base_sha": v["base_commit_sha"],
        "head_sha": v["head_commit_sha"],
        "start_sha": v["start_commit_sha"],
    }


def position(refs: dict, file: str, line: int, *, old_line: int | None = None) -> dict:
    pos = {
        "position_type": "text",
        "new_path": file,
        "old_path": file,
        "new_line": line,
        **refs,
    }
    if old_line is not None:
        pos["old_line"] = old_line
        if line is None:
            pos.pop("new_line", None)
    return pos


def post_one(host, project, iid, refs, file, line, body, *, old_line=None) -> dict:
    payload = {"body": body, "position": position(refs, file, line, old_line=old_line)}
    disc = api(
        host,
        f"projects/{project}/merge_requests/{iid}/discussions",
        method="POST",
        payload=payload,
    )
    note = disc["notes"][0]
    got_line = (note.get("position") or {}).get("new_line")
    if note.get("type") != "DiffNote" or (line is not None and got_line != line):
        api(
            host,
            f"projects/{project}/merge_requests/{iid}/notes/{note['id']}",
            method="DELETE",
        )
        sys.exit(
            f"NOT inline ({note.get('type')}, line={got_line}) for {file}:{line} — "
            "note deleted. The line is probably not part of the diff: anchor the "
            "finding to a changed line, or pass --old-line for a removed one."
        )
    return {"thread": disc["id"], "note": note["id"], "file": file, "line": line}


def gated(review_dir: str, items: list[dict]) -> list[tuple]:
    """Only what passed the gate may be posted: (file, line, old_line, body) per item.

    An item is either a `finding.py render --json` row ({"location", "body"}, optional
    "old_line") or {"file", "line"|"old_line", "body"|"body_file"}. Its body must equal
    `finding.render_comment` of a finding recorded at that location. Refuses the whole
    batch before anything is posted.
    """
    try:
        state = finding.load_state(review_dir)
    except finding.Refused as exc:
        sys.exit(f"REFUSED: {exc}\nOnly findings that passed finding.py are posted; "
                 "a question to the author — post --question.")
    allowed = {(f["location"], finding.render_comment(f).rstrip("\n")) for f in state["findings"]}
    out, bad = [], []
    for item in items:
        body = item.get("body")
        if body is None:
            body = open(item["body_file"], encoding="utf-8").read()
        if "location" in item:
            location = item["location"]
            file, _, num = location.rpartition(":")
            old = item.get("old_line")
            line = None if old is not None else int(num)
        else:
            file, line, old = item["file"], item.get("line"), item.get("old_line")
            location = f"{file}:{line if line is not None else old}"
        if (location, body.rstrip("\n")) not in allowed:
            bad.append(location)
        out.append((file, line, old, body))
    if bad:
        sys.exit("REFUSED: not a finding that passed finding.py (its text or line differs): "
                 + ", ".join(bad) + "\nRecord it with `finding.py add` and post the output of "
                 "`finding.py render --json` unchanged.")
    return out


def question_body(body: str) -> str:
    """A question claims nothing: no verdict and none of a finding's sections."""
    first = body.strip().splitlines()[0] if body.strip() else ""
    if finding.CONFIRMED in first or finding.ASSUMED in first or "**Ломается при:**" in body:
        sys.exit("REFUSED: this is a finding, not a question — it carries a verdict or a failure "
                 "scenario. Pass it through finding.py and post it without --question.")
    return body


def cmd_post(args):
    project, iid = parse_mr(args.mr)
    body = args.body if args.body else open(args.body_file, encoding="utf-8").read()
    if args.question:
        file, line, old, body = args.file, args.line, args.old_line, question_body(body)
    else:
        [(file, line, old, body)] = gated(
            args.dir, [{"file": args.file, "line": args.line, "old_line": args.old_line, "body": body}])
    refs = diff_refs(args.host, project, iid)
    res = post_one(args.host, project, iid, refs, file, line, body, old_line=old)
    print(f"inline ok  {res['file']}:{res['line']}  thread={res['thread']} note={res['note']}")


def cmd_post_batch(args):
    project, iid = parse_mr(args.mr)
    items = gated(args.dir, json.load(open(args.input, encoding="utf-8")))
    refs = diff_refs(args.host, project, iid)
    for file, line, old, body in items:
        res = post_one(args.host, project, iid, refs, file, line, body, old_line=old)
        print(f"inline ok  {res['file']}:{res['line']}  thread={res['thread']} note={res['note']}")


def cmd_threads(args):
    project, iid = parse_mr(args.mr)
    page, seen = 1, 0
    while True:
        chunk = api(
            args.host,
            f"projects/{project}/merge_requests/{iid}/discussions"
            f"?per_page=100&page={page}",
        )
        if not chunk:
            break
        for d in chunk:
            note = d["notes"][0]
            if not args.all and not note["body"].startswith("**[ai-review-bot]**"):
                continue
            pos = note.get("position") or {}
            where = f"{pos.get('new_path')}:{pos.get('new_line')}" if pos else "MR-level"
            state = "resolved" if note.get("resolved") else "open"
            kind = note.get("type") or "Note"
            print(f"{d['id'][:12]}  {state:8} {kind:9} {where}")
            print(f"    {note['body'].splitlines()[0][:100]}")
            seen += 1
        page += 1
    if not seen:
        print("no [ai-review-bot] threads")


def cmd_reply(args):
    project, iid = parse_mr(args.mr)
    body = args.body if args.body else open(args.body_file, encoding="utf-8").read()
    note = api(
        args.host,
        f"projects/{project}/merge_requests/{iid}/discussions/{args.thread}/notes",
        method="POST",
        payload={"body": body},
    )
    print(f"replied in {args.thread} note={note['id']}")


def cmd_resolve(args):
    project, iid = parse_mr(args.mr)
    api(
        args.host,
        f"projects/{project}/merge_requests/{iid}/discussions/{args.thread}",
        method="PUT",
        payload={"resolved": True},
    )
    print(f"resolved {args.thread}")


def cmd_delete(args):
    project, iid = parse_mr(args.mr)
    api(
        args.host,
        f"projects/{project}/merge_requests/{iid}/notes/{args.note}",
        method="DELETE",
    )
    print(f"deleted note {args.note}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--dir", default=".", help="where finding.py keeps .review/ (default: .)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def with_mr(sp):
        sp.add_argument("--mr", required=True, help="group/project!iid")
        return sp

    sp = with_mr(sub.add_parser("post", help="one inline comment"))
    sp.add_argument("--file", required=True)
    sp.add_argument("--line", type=int, help="line in the NEW file")
    sp.add_argument("--old-line", type=int, help="line in the OLD file (removed line)")
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--body")
    g.add_argument("--body-file")
    sp.add_argument("--question", action="store_true",
                    help="a question to the author: claims nothing, so it skips the finding.py gate")
    sp.set_defaults(func=cmd_post)

    sp = with_mr(sub.add_parser("post-batch", help="many inline comments from JSON"))
    sp.add_argument("--input", required=True,
                    help='`finding.py render --json` output, or [{"file","line"|"old_line","body"|"body_file"}, ...]')
    sp.set_defaults(func=cmd_post_batch)

    sp = with_mr(sub.add_parser("threads", help="list review threads"))
    sp.add_argument("--all", action="store_true", help="not only [ai-review-bot]")
    sp.set_defaults(func=cmd_threads)

    sp = with_mr(sub.add_parser("reply", help="reply into a thread"))
    sp.add_argument("--thread", required=True)
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--body")
    g.add_argument("--body-file")
    sp.set_defaults(func=cmd_reply)

    sp = with_mr(sub.add_parser("resolve", help="resolve a thread"))
    sp.add_argument("--thread", required=True)
    sp.set_defaults(func=cmd_resolve)

    sp = with_mr(sub.add_parser("delete", help="delete a note"))
    sp.add_argument("--note", required=True)
    sp.set_defaults(func=cmd_delete)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
