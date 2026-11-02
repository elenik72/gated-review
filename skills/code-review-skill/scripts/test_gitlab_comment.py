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
        [(file, line, old, body, resolve)] = gitlab_comment.gated(self.root, self.rendered())
        self.assertEqual((file, line, old, resolve), ("src/MediaTable.tsx", 64, None, False))
        self.assertTrue(body.startswith("**[ai-review-bot]**"))

    def test_file_line_form_with_a_trailing_newline_is_accepted(self):
        body = self.rendered()[0]["body"] + "\n"
        [(file, line, _, _, _)] = gitlab_comment.gated(
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

    def test_a_note_is_posted_and_resolved_a_finding_stays_open(self):
        self.cli("fyi", "--location", "src/MediaTable.tsx:70", "--text",
                 "Тот же список рендерит MediaGrid", "--source", "src/MediaGrid.tsx:12")
        path = os.path.join(self.root, "out.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.rendered(), fh, ensure_ascii=False)
        calls = []
        posted = lambda h, p, i, r, f, l, b, old_line=None: {"file": f, "line": l, "thread": "t%d" % l, "note": 1}
        with mock.patch.object(gitlab_comment, "diff_refs", return_value={}), \
             mock.patch.object(gitlab_comment, "post_one", side_effect=posted), \
             mock.patch.object(gitlab_comment, "api", side_effect=lambda *a, **k: calls.append(a[1])), \
             contextlib.redirect_stdout(io.StringIO()):
            gitlab_comment.cmd_post_batch(mock.Mock(mr="g/p!1", host="h", dir=self.root, input=path))
        self.assertEqual(calls, ["projects/g%2Fp/merge_requests/1/discussions/t70"])

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
