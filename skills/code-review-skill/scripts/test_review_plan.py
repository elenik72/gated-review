#!/usr/bin/env python3
"""Tests for review_plan.py: the stack comes from the changed files, the commands from the repo."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import review_plan


def sh(cwd, *cmd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


class FixtureRepo(unittest.TestCase):
    """main has manifests; the feature branch changes one FastAPI and one React file."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        r = self.root
        (r / "api").mkdir()
        (r / "web" / "src").mkdir(parents=True)
        (r / "pyproject.toml").write_text(
            '[project]\nname = "svc"\ndependencies = ["fastapi>=0.120", "pydantic>=2"]\n'
            '[dependency-groups]\ndev = ["pytest", "ruff", "mypy"]\n[tool.ruff]\nline-length = 100\n')
        (r / "uv.lock").write_text("version = 1\n")
        (r / "web" / "package.json").write_text(json.dumps({
            "dependencies": {"react": "19.3.0", "@tanstack/react-query": "5"},
            "devDependencies": {"typescript": "6", "eslint": "10", "vitest": "5", "knip": "6"}}))
        (r / "web" / "tsconfig.json").write_text("{}")
        (r / "web" / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n")
        (r / "AGENTS.md").write_text("# rules\n\n## Code Review Rules\n- services never import routers\n")
        (r / "web" / "eslint.config.js").write_text("export default []\n")
        (r / "api" / "main.py").write_text("x = 1\n")
        (r / "web" / "src" / "App.tsx").write_text("export const A = 1\n")
        sh(r, "git", "init", "-q", "-b", "main")
        sh(r, "git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
        sh(r, "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
        sh(r, "git", "checkout", "-qb", "feature")
        (r / "api" / "main.py").write_text("x = 2\n")
        (r / "web" / "src" / "App.tsx").write_text("export const A = 2\n")
        sh(r, "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "change")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_detects_both_stacks_from_the_diff(self):
        found, rules = review_plan.detect(self.root, "main")
        self.assertEqual(sorted(found), ["python-fastapi", "ts-react"])
        self.assertEqual(found["ts-react"]["files"], ["web/src/App.tsx"])
        self.assertIn("AGENTS.md", rules)
        self.assertIn("web/eslint.config.js", rules)

    def test_plan_uses_the_repo_runners_and_tools(self):
        text, stacks = review_plan.build(self.root, "design", None, "main")
        self.assertEqual(stacks, ["python-fastapi", "ts-react"])
        self.assertIn("uv run --frozen ruff check", text)
        self.assertIn("uv run --frozen mypy", text)
        self.assertIn("PYTHONASYNCIODEBUG=1 uv run --frozen pytest", text)
        self.assertIn("pnpm exec tsc --noEmit -p web/tsconfig.json", text)
        self.assertIn("pnpm exec vitest related --run", text)
        self.assertIn("reference/python-fastapi.md", text)
        self.assertIn("reference/react-modern-stack.md", text)  # TanStack Query is a dependency
        self.assertNotIn("pyright", text)                       # the repo does not use it
        self.assertNotIn("playwright", text)

    def test_show_writes_nothing_init_writes_file_lists(self):
        review_plan.build(self.root, "full", None, "main")
        self.assertFalse((self.root / ".review").exists())
        review_plan.build(self.root, "full", None, "main", write_lists=True)
        self.assertEqual((self.root / ".review" / "py.txt").read_text(), "api/main.py\n")

    def test_business_mode_announces_the_requirements_gate(self):
        text, _ = review_plan.build(self.root, "business", ["python-fastapi"], "main")
        self.assertIn("render откажет без требований", text)
        self.assertNotIn("ts-react", text)

    def test_unknown_stack_is_rejected(self):
        with self.assertRaises(ValueError):
            review_plan.parse_stacks("ruby")


if __name__ == "__main__":
    os.environ.pop("GIT_DIR", None)
    unittest.main()
