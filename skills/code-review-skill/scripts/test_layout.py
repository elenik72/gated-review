#!/usr/bin/env python3
"""Packaging checks that turn silent failures into test failures (stdlib unittest, no network).

A broken link, a script the docs name but the plugin does not ship, or two manifests with
different versions all load without an error — the agent just reads less than it should.
"""

import json
import py_compile
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
PLUGIN = SKILL.parents[1]
FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LINK = re.compile(r"\]\(([^)\s]+)\)")
SCRIPT_REF = re.compile(r"scripts/([\w.-]+\.py)")


def slug(text):
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text).replace("`", "").replace("*", "")
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")


def outside_code(path):
    in_code = False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE.match(line):
            in_code = not in_code
        elif not in_code:
            yield n, line


def anchors(path):
    seen, out = {}, set()
    for _, line in outside_code(path):
        m = HEADING.match(line)
        if m:
            base = slug(m.group(2))
            out.add(base if base not in seen else "%s-%d" % (base, seen[base]))
            seen[base] = seen.get(base, 0) + 1
    return out


class LayoutTest(unittest.TestCase):
    def test_manifests_agree(self):
        claude = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
        codex = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
        for key in ("name", "version", "description", "license"):
            self.assertEqual(claude[key], codex[key], key)

    def test_frontmatter_names_the_skill_and_its_triggers(self):
        head = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("---")[1]
        self.assertIn("name: %s" % SKILL.name, head)
        self.assertIn("ALWAYS invoke", head)

    def test_the_skill_survives_a_context_compaction_whole(self):
        # Claude Code re-attaches an invoked skill cut to its first 5,000 tokens after a compaction;
        # what a review needs only at one step lives in reference/, read from disk at that step.
        size = len((SKILL / "SKILL.md").read_text(encoding="utf-8"))
        self.assertLessEqual(size, 19_000, "SKILL.md is %d characters: move a section to reference/" % size)

    def test_links_and_anchors_resolve(self):
        broken = []
        for md in SKILL.rglob("*.md"):
            for n, line in outside_code(md):
                for target in LINK.findall(line):
                    if re.match(r"^[a-z]+://", target):
                        continue
                    path, _, anchor = target.partition("#")
                    dest = (md.parent / path).resolve() if path else md
                    if not dest.exists() or (anchor and dest.suffix == ".md" and anchor not in anchors(dest)):
                        broken.append("%s:%d %s" % (md.relative_to(SKILL), n, target))
        self.assertEqual(broken, [])

    def test_named_scripts_ship_and_compile(self):
        named = set()
        for md in SKILL.rglob("*.md"):
            named |= set(SCRIPT_REF.findall(md.read_text(encoding="utf-8")))
        missing = sorted(n for n in named if not (SKILL / "scripts" / n).exists())
        self.assertEqual(missing, [])
        for script in (SKILL / "scripts").glob("*.py"):
            py_compile.compile(str(script), doraise=True)


if __name__ == "__main__":
    unittest.main()
