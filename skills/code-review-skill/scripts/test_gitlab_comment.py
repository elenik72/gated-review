#!/usr/bin/env python3
"""Tests for the posting gate in gitlab_comment.py (stdlib unittest, no network).

Only the part that decides what may be posted is tested: a comment reaches the MR only
if finding.py produced it for that exact line.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import finding
import gitlab_comment


class PostGateTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.cli("init")
        self.cli("cover", "--add", "src/**")
        self.cli("add", "--form", "breaks", "--severity", "blocking", "--rung", "3",
                 "--claim", "MediaTable падает на пустом списке",
                 "--breaks-when", "items = [] -> белый экран вместо пустого состояния",
                 "--location", "src/MediaTable.tsx:64",
                 "--evidence", "pnpm vitest run media.spec.ts", "--output", "1 failed")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(finding.main(["--dir", self.root] + list(argv)), 0)
        return out.getvalue()

    def rendered(self):
        return json.loads(self.cli("render", "--json"))

    def refused(self, items):
        with self.assertRaises(SystemExit) as ctx:
            gitlab_comment.gated(self.root, items)
        return str(ctx.exception.code)

    def test_render_json_is_accepted_as_is(self):
        [(file, line, old, body)] = gitlab_comment.gated(self.root, self.rendered())
        self.assertEqual((file, line, old), ("src/MediaTable.tsx", 64, None))
        self.assertTrue(body.startswith("**[ai-review-bot]**"))

    def test_file_line_form_with_a_trailing_newline_is_accepted(self):
        body = self.rendered()[0]["body"] + "\n"
        [(file, line, _, _)] = gitlab_comment.gated(
            self.root, [{"file": "src/MediaTable.tsx", "line": 64, "body": body}])
        self.assertEqual((file, line), ("src/MediaTable.tsx", 64))

    def test_an_edited_body_is_refused(self):
        items = self.rendered()
        items[0]["body"] = items[0]["body"].replace("подтверждено", "подтверждено, точно")
        self.assertIn("src/MediaTable.tsx:64", self.refused(items))

    def test_a_hand_written_comment_is_refused(self):
        self.refused([{"file": "src/Other.tsx", "line": 3,
                       "body": "**[ai-review-bot]** · Приоритет: важно · Блокирующее: да · подтверждено"}])

    def test_the_same_body_on_another_line_is_refused(self):
        items = self.rendered()
        items[0]["location"] = "src/MediaTable.tsx:65"
        self.refused(items)

    def test_one_bad_item_refuses_the_whole_batch(self):
        good = self.rendered()[0]
        self.refused([good, dict(good, location="src/MediaTable.tsx:99")])

    def test_no_review_state_is_refused(self):
        with self.assertRaises(SystemExit) as ctx:
            gitlab_comment.gated(tempfile.mkdtemp(), [{"location": "a.ts:1", "body": "x"}])
        self.assertIn("--question", str(ctx.exception.code))

    def post_batch_with_notes(self, notes, api_reply=None):
        """post-batch the finding of setUp and `notes` (line, text); returns what went where."""
        for line, text in notes:
            self.cli("fyi", "--location", "src/MediaTable.tsx:%d" % line, "--text", text,
                     "--source", "src/MediaGrid.tsx:12")
        path = os.path.join(self.root, "out.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.rendered(), fh, ensure_ascii=False)
        calls, lines, out = [], [], io.StringIO()
        def posted(h, p, i, r, f, l, b, old_line=None):
            lines.append(l)
            return {"file": f, "line": l, "thread": "t%d" % l, "note": 1}
        def api(host, path, **kw):
            calls.append((path, kw))
            return api_reply or {"id": 7, "type": None, "resolvable": False}
        with mock.patch.object(gitlab_comment, "diff_refs", return_value={"head_sha": "abc1234"}), \
             mock.patch.object(gitlab_comment, "check_head"), \
             mock.patch.object(gitlab_comment, "post_one", side_effect=posted), \
             mock.patch.object(gitlab_comment, "api", side_effect=api), \
             contextlib.redirect_stdout(out):
            gitlab_comment.cmd_post_batch(mock.Mock(mr="g/p!1", host="h", dir=self.root, input=path))
        return lines, calls, out.getvalue()

    def test_notes_go_into_one_plain_comment_not_into_threads(self):
        # an open thread held the merge; closed at posting, it was folded away before it was read
        lines, calls, out = self.post_batch_with_notes(
            [(70, "Тот же список рендерит MediaGrid"), (90, "Сортировку меняет соседний MR")])
        self.assertEqual(lines, [64])  # only the finding is a thread on its line
        [(path, kw)] = calls  # one request for both notes, and nothing is resolved
        self.assertEqual((path, kw["method"]), ("projects/g%2Fp/merge_requests/1/notes", "POST"))
        body = kw["payload"]["body"]
        self.assertTrue(body.startswith(finding.FYI_HEAD + "\n"))
        self.assertEqual(body.count(finding.FYI_HEAD), 1)  # the header once, not per note
        self.assertIn("[`src/MediaTable.tsx:70`](https://h/g/p/-/blob/abc1234/src/MediaTable.tsx#L70)", body)
        self.assertIn("Сортировку меняет соседний MR", body)
        self.assertIn("**Источник:** src/MediaGrid.tsx:12", body)
        self.assertIn("note ok  src/MediaTable.tsx:70  comment=7", out)
        self.assertIn("note ok  src/MediaTable.tsx:90  comment=7", out)

    def test_a_review_without_notes_posts_no_comment(self):
        lines, calls, out = self.post_batch_with_notes([])
        self.assertEqual((lines, calls), ([64], []))
        self.assertNotIn("note ok", out)

    def test_notes_that_came_back_as_a_thread_are_deleted(self):
        with self.assertRaises(SystemExit) as ctx:
            self.post_batch_with_notes([(70, "Тот же список рендерит MediaGrid")],
                                       api_reply={"id": 7, "type": "DiscussionNote", "resolvable": True})
        self.assertIn("holds the merge", str(ctx.exception.code))

    def test_one_note_posted_alone_is_a_plain_comment_too(self):
        self.cli("fyi", "--location", "src/MediaTable.tsx:70", "--text",
                 "Тот же список рендерит MediaGrid", "--source", "src/MediaGrid.tsx:12")
        note = [c for c in self.rendered() if c["kind"] == "note"][0]
        calls = []
        def api(host, path, **kw):
            calls.append(path)
            return {"id": 9, "type": None, "resolvable": False}
        with mock.patch.object(gitlab_comment, "diff_refs", return_value={}), \
             mock.patch.object(gitlab_comment, "check_head"), \
             mock.patch.object(gitlab_comment, "post_one") as inline, \
             mock.patch.object(gitlab_comment, "api", side_effect=api), \
             contextlib.redirect_stdout(io.StringIO()):
            gitlab_comment.cmd_post(mock.Mock(
                mr="g/p!1", host="h", dir=self.root, file="src/MediaTable.tsx", line=70,
                old_line=None, body=note["body"], body_file=None, question=False))
        self.assertEqual((calls, inline.call_count), (["projects/g%2Fp/merge_requests/1/notes"], 0))

    def test_threads_shows_a_plain_comment_as_not_a_thread(self):
        page = [{"id": "d1" * 6, "notes": [{"body": finding.FYI_HEAD + "\n\n…", "resolved": False,
                                            "resolvable": False, "type": None}]},
                {"id": "d2" * 6, "notes": [{"body": "**[ai-review-bot]** · 🐞 Баг · желательно · подтверждено",
                                            "resolved": False, "resolvable": True, "type": "DiffNote",
                                            "position": {"new_path": "a.rb", "new_line": 3}}]}]
        out = io.StringIO()
        with mock.patch.object(gitlab_comment, "api", side_effect=[page, []]), \
             contextlib.redirect_stdout(out):
            gitlab_comment.cmd_threads(mock.Mock(mr="g/p!1", host="h", all=False))
        first, _, second, _ = out.getvalue().splitlines()
        self.assertIn("comment", first)
        self.assertIn("open", second)

    def test_reopen_opens_a_resolved_thread_again(self):
        calls = []
        with mock.patch.object(gitlab_comment, "api", side_effect=lambda *a, **k: calls.append((a[1], k))), \
             contextlib.redirect_stdout(io.StringIO()):
            gitlab_comment.cmd_resolve(mock.Mock(mr="g/p!1", host="h", thread="t70", reopen=True))
        self.assertEqual(calls, [("projects/g%2Fp/merge_requests/1/discussions/t70",
                                  {"method": "PUT", "payload": {"resolved": False}})])

    def post_batch_on(self, mr_head):
        """post-batch the rendered findings against an MR whose head is `mr_head`; returns post_one."""
        state = finding.load_state(self.root)
        state["head"] = "abc1234"
        finding.save_state(self.root, state)
        path = os.path.join(self.root, "out.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.rendered(), fh, ensure_ascii=False)
        posted = mock.Mock(return_value={"file": "f", "line": 1, "thread": "t", "note": 1})
        with mock.patch.object(gitlab_comment, "diff_refs", return_value={"head_sha": mr_head}), \
             mock.patch.object(gitlab_comment, "post_one", posted), \
             contextlib.redirect_stdout(io.StringIO()):
            gitlab_comment.cmd_post_batch(mock.Mock(mr="g/p!1", host="h", dir=self.root, input=path))
        return posted

    def test_nothing_is_posted_once_the_mr_moved_on(self):
        with self.assertRaises(SystemExit) as ctx:
            self.post_batch_on("fff0000000000000000000000000000000000000")
        self.assertIn("rehead", str(ctx.exception.code))

    def test_the_reviewed_head_is_posted(self):
        self.assertEqual(self.post_batch_on("abc1234def0000000000000000000000000000000").call_count, 1)

    def test_a_question_without_a_review_state_is_not_held(self):
        gitlab_comment.check_head(tempfile.mkdtemp(), {"head_sha": "fff0000"})

    def test_a_question_passes_without_the_gate(self):
        q = "**[ai-review-bot]** · ❓ Вопрос\n\nПочему здесь не используется общий хук?"
        self.assertEqual(gitlab_comment.question_body(q), q)

    def test_a_question_without_the_bot_header_is_refused(self):
        for q in ("Почему здесь не используется общий хук?",
                  "**[ai-review-bot]** · Приоритет: не важно · Блокирующее: нет\n\nПочему не общий хук?"):
            with self.assertRaises(SystemExit):
                gitlab_comment.question_body(q)

    def test_a_reply_keeps_the_bot_tag(self):
        ok = "**[ai-review-bot]** · Приоритет: важно · Блокирующее: да · подтверждено\n\nИсправлено в a1b2c3d."
        self.assertEqual(gitlab_comment.bot_body(ok, "a reply"), ok)
        with self.assertRaises(SystemExit):
            gitlab_comment.bot_body("Исправлено, спасибо!", "a reply")

    def test_a_finding_cannot_hide_behind_question(self):
        with self.assertRaises(SystemExit):
            gitlab_comment.question_body(self.rendered()[0]["body"])


class UnsafeBodyTest(unittest.TestCase):
    """A reply never went through `finding.py add`: the posting script is its only door."""

    def test_a_body_gitlab_would_run_is_not_sent(self):
        with mock.patch.object(gitlab_comment, "token", return_value="t"), \
             mock.patch.object(gitlab_comment.urllib.request, "urlopen") as sent:
            with self.assertRaises(SystemExit) as stop:
                gitlab_comment.api("gitlab.example.com", "projects/1/merge_requests/2/notes", method="POST",
                                   payload={"body": "**[ai-review-bot]**\n/approve"})
        self.assertIn("/approve", str(stop.exception))
        sent.assert_not_called()


class AnchorTest(unittest.TestCase):
    """GitLab anchors a comment on a line the change kept by both its numbers and refuses one
    with the new number alone (`line_code can't be blank`)."""

    DIFF = "\n".join([
        "@@ -17,8 +17,6 @@ class Config",
        " ",
        "     NAME = 'name'",
        "-    # legacy",
        "-    LEGACY = 'old'",
        "     SCHEMA = {",
        "       'name' => { type: String },",
        "-      'legacy' => {},",
        "+      'label' => {},",
        "       'options' => {",
        "@@ -40,3 +38,4 @@ class Config",
        "   def a",
        "+    b",
        "   end",
        "   x",
        "\\ No newline at end of file",
    ])

    def test_old_numbers_of_kept_lines_and_none_for_added_ones(self):
        # kept in a hunk, added, before the first hunk, between hunks, added, kept, after the last
        for line, old in ((20, 22), (21, None), (10, 10), (30, 32), (39, None), (41, 42), (50, 51)):
            self.assertEqual(gitlab_comment.old_line_of(self.DIFF, line), old, line)

    def test_a_comment_on_a_kept_line_carries_both_numbers(self):
        gitlab_comment.file_diffs.cache_clear()
        sent = []

        def api(host, path, method="GET", payload=None):
            if path.endswith("/versions"):
                return [{"id": 7, "head_commit_sha": "h"}]
            if path.endswith("/versions/7"):
                return {"diffs": [{"new_path": "a.rb", "old_path": "a.rb", "diff": self.DIFF}]}
            sent.append(payload["position"])
            return {"id": "d", "notes": [{"id": 5, "type": "DiffNote", "position": {"new_line": sent[-1]["new_line"]}}]}

        with mock.patch.object(gitlab_comment, "api", side_effect=api):
            for line in (20, 21):
                gitlab_comment.post_one("h", "g%2Fp", "1", {"head_sha": "h"}, "a.rb", line, "x")
        self.assertEqual([(p["new_line"], p.get("old_line")) for p in sent], [(20, 22), (21, None)])


class HostTest(unittest.TestCase):
    """No host is baked in: it comes from --host, GITLAB_HOST or the reviewed repo's origin."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.env = mock.patch.dict(os.environ)
        self.env.start()
        os.environ.pop("GITLAB_HOST", None)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.repo, ignore_errors=True)

    def origin(self, url):
        subprocess.run(["git", "-C", self.repo, "remote", "add", "origin", url], check=True)

    def test_origin_url_forms(self):
        for url, host in [
            ("git@gitlab.example.com:group/project.git", "gitlab.example.com"),
            ("https://gitlab.example.com/group/project.git", "gitlab.example.com"),
            ("ssh://git@gitlab.example.com:2222/group/project.git", "gitlab.example.com"),
        ]:
            subprocess.run(["git", "-C", self.repo, "remote", "remove", "origin"],
                           capture_output=True)
            self.origin(url)
            self.assertEqual(gitlab_comment.resolve_host(None, self.repo), host, url)

    def test_flag_beats_env_beats_origin(self):
        self.origin("git@gitlab.example.com:group/project.git")
        os.environ["GITLAB_HOST"] = "env.example.com"
        self.assertEqual(gitlab_comment.resolve_host("flag.example.com", self.repo),
                         "flag.example.com")
        self.assertEqual(gitlab_comment.resolve_host(None, self.repo), "env.example.com")

    def test_no_origin_and_no_flag_exits(self):
        with self.assertRaises(SystemExit):
            gitlab_comment.resolve_host(None, self.repo)

    def test_github_origin_is_refused(self):
        self.origin("git@github.com:owner/repo.git")
        with self.assertRaises(SystemExit):
            gitlab_comment.resolve_host(None, self.repo)


if __name__ == "__main__":
    unittest.main()
