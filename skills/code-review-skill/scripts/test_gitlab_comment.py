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
import tempfile
import unittest

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

    def test_a_question_passes_without_the_gate(self):
        q = "**[ai-review-bot]** · Вопрос\n\nПочему здесь не используется общий хук?"
        self.assertEqual(gitlab_comment.question_body(q), q)

    def test_a_finding_cannot_hide_behind_question(self):
        with self.assertRaises(SystemExit):
            gitlab_comment.question_body(self.rendered()[0]["body"])


if __name__ == "__main__":
    unittest.main()
