#!/usr/bin/env python3
"""review_plan.py — what to read and which checks to run for a review mode and a stack.

One registry for modes and stacks. `finding.py init --mode … --stack …` stores the choice and
prints this plan; REVIEW-NOTES.md repeats its header, so it survives a context compaction.

  review_plan.py detect [--dir .] [--target origin/main] [--json]
      stacks found in the changed files, and the repo files that act as its style guide
  review_plan.py show --mode full|business|design|security [--stack auto|<stack>,…] [--target …]
      the plan: what to read, which rules are the repo's own, the ladder commands for this repo

Read-only, stdlib only. Commands are built from what the repo already has (lockfile, configs,
dependencies); a tool the repo does not use is not suggested — probes live in the references.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# the registry
# ═══════════════════════════════════════════════════════════════

MODES = {
    "full": {
        "title": "полное ревью: логика, требования, дизайн, безопасность, производительность",
        "refs": ["reference/architecture-review-guide.md", "reference/code-quality-universal.md",
                 "reference/security-review-guide.md", "reference/performance-review-guide.md"],
        "forms": "все формы; требования тикета — таблица в Phase 4",
        "max_nits": 5,
        "needs_requirements": False,
    },
    "business": {
        "title": "бизнес-логика: реализовано ли то, что требует тикет, и правильно ли",
        "refs": ["reference/business-logic-review.md"],
        "forms": "unimplemented, breaks, invariant, unrequested",
        "max_nits": 0,
        "needs_requirements": True,
    },
    "design": {
        "title": "стайлгайд, архитектура и дизайн кода по правилам самого репо",
        "refs": ["reference/design-review.md", "reference/architecture-review-guide.md",
                 "reference/code-quality-universal.md"],
        "forms": "rule, drift, unread, invariant",
        "max_nits": 5,
        "needs_requirements": False,
    },
    "security": {
        "title": "безопасность: инъекции, доступ, секреты, небезопасные API",
        "refs": ["reference/security-review-guide.md", "reference/cross-cutting/sql-injection-prevention.md",
                 "reference/cross-cutting/xss-prevention.md"],
        "forms": "breaks, invariant",
        "max_nits": 0,
        "needs_requirements": False,
    },
}

STACKS = {
    "ts-react": {"title": "TypeScript + React (SPA)", "lang": "js",
                 "refs": ["reference/react.md", "reference/react-checks.md", "reference/typescript.md",
                          "reference/frontend-web-specifics.md"],
                 "if_dep": {"@tanstack/react-query": "reference/react-modern-stack.md"}},
    "node-nestjs": {"title": "Node.js + NestJS", "lang": "js",
                    "refs": ["reference/nestjs.md", "reference/typescript.md"]},
    "typescript": {"title": "TypeScript / JavaScript без фреймворка", "lang": "js",
                   "refs": ["reference/typescript.md"]},
    "python-fastapi": {"title": "Python + FastAPI (asyncio)", "lang": "py",
                       "refs": ["reference/python.md", "reference/python-fastapi.md"]},
    "python": {"title": "Python без FastAPI", "lang": "py", "refs": ["reference/python.md"]},
}

LANG_EXT = {
    "js": (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"),
    "py": (".py", ".pyi"),
}

# files that act as the repo's own style guide / review rules, first wins
RULE_FILE = re.compile(
    r"(^|/)(AGENTS\.md|CLAUDE\.md|REVIEW\.md|CONTRIBUTING\.md|\.editorconfig|"
    r"eslint\.config\.[cm]?[jt]s|\.eslintrc(\.\w+)?|biome\.jsonc?|\.prettierrc(\.\w+)?|"
    r"ruff\.toml|\.ruff\.toml|\.importlinter|\.dependency-cruiser\.[cm]?js(on)?|"
    r"\.github/copilot-instructions\.md|\.coderabbit\.ya?ml|\.cursor/BUGBOT\.md)$"
    r"|(^|/)docs?/.*(style|convention|guideline|architecture|adr|code-review).*\.md$",
    re.I,
)


# ═══════════════════════════════════════════════════════════════
# repo facts
# ═══════════════════════════════════════════════════════════════

def git(root, *args):
    try:
        p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30)
    except OSError:
        return ""
    return p.stdout if p.returncode == 0 else ""


def default_target(root):
    ref = git(root, "rev-parse", "--abbrev-ref", "origin/HEAD").strip()
    return ref if ref and ref != "origin/HEAD" else ""


def changed_files(root, target):
    if not target:
        return []
    out = git(root, "diff", "--name-only", "--diff-filter=d", f"{target}...HEAD")
    if not out and "/" not in target:  # "main" is usually meant as "origin/main"
        out = git(root, "diff", "--name-only", "--diff-filter=d", f"origin/{target}...HEAD")
    return [f for f in out.splitlines() if f.strip()]


def nearest(root, rel, names):
    """Closest directory (relative to root) above `rel` that holds one of `names`."""
    d = (root / rel).parent
    while True:
        for n in names:
            if (d / n).is_file():
                return d
        if d == root or root not in d.parents:
            return root if any((root / n).is_file() for n in names) else None
        d = d.parent


def read(p):
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def js_deps(pkg_dir):
    try:
        data = json.loads(read(pkg_dir / "package.json") or "{}")
    except ValueError:
        return {}, {}
    deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps.update(data.get(key) or {})
    return deps, data


def py_manifest_text(d):
    parts = [read(d / "pyproject.toml")] + [read(p) for p in sorted(d.glob("requirements*.txt"))]
    return "\n".join(parts)


def classify(root, rel):
    """(stack, manifest dir) for one changed file, or (None, None)."""
    if rel.endswith(LANG_EXT["js"]):
        d = nearest(root, rel, ["package.json"])
        if d is None:
            return "typescript", root
        deps, _ = js_deps(d)
        if "@nestjs/core" in deps:
            return "node-nestjs", d
        if "react" in deps:
            return "ts-react", d
        return "typescript", d
    if rel.endswith(LANG_EXT["py"]):
        d = nearest(root, rel, ["pyproject.toml", "requirements.txt"]) or root
        if re.search(r"(?im)^\s*[\"']?fastapi\b", py_manifest_text(d)) or \
           re.search(r"(?i)[\"']fastapi[\"'>=<~\[ ]", py_manifest_text(d)):
            return "python-fastapi", d
        return "python", d
    return None, None


def detect(root, target):
    """{stack: {"files": [...], "dirs": {manifest dirs}}} plus the repo rule files."""
    found = {}
    for rel in changed_files(root, target):
        stack, d = classify(root, rel)
        if stack:
            entry = found.setdefault(stack, {"files": [], "dirs": set()})
            entry["files"].append(rel)
            entry["dirs"].add(d)
    if not found:  # no diff to read: fall back to the manifests at the root
        if (root / "package.json").is_file():
            stack, _ = classify(root, "x.ts")
            found[stack] = {"files": [], "dirs": {root}}
        if (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file():
            stack, _ = classify(root, "x.py")
            found[stack] = {"files": [], "dirs": {root}}
    changed = [f for e in found.values() for f in e["files"]]
    def applies(rule):  # a rule file in the root, or in a directory the change touches
        parent = str(Path(rule).parent)
        return parent == "." or not changed or any(f.startswith(parent + "/") for f in changed)
    rules = [f for f in git(root, "ls-files").splitlines() if RULE_FILE.search(f) and applies(f)]
    tools = sorted(set(re.findall(r"(?m)^\[tool\.(ruff|importlinter)\b", read(root / "pyproject.toml"))))
    if tools:
        rules.append("pyproject.toml (%s)" % ", ".join("[tool.%s]" % t for t in tools))
    return found, rules[:15]


# ═══════════════════════════════════════════════════════════════
# the ladder, from what the repo has
# ═══════════════════════════════════════════════════════════════

def js_runner(root, d):
    _, data = js_deps(d)
    pm = str(data.get("packageManager") or "")
    for base in (d, root):
        if pm.startswith("pnpm") or (base / "pnpm-lock.yaml").is_file():
            return "pnpm exec"
        if pm.startswith("yarn") or (base / "yarn.lock").is_file():
            return "yarn"
        if pm.startswith("bun") or (base / "bun.lock").is_file() or (base / "bun.lockb").is_file():
            return "bunx"
    return "npx --no"


def py_runner(root, d):
    for base in (d, root):
        if (base / "uv.lock").is_file():
            return "uv run --frozen"
        if (base / "poetry.lock").is_file():
            return "poetry run"
        if (base / "pdm.lock").is_file():
            return "pdm run"
    return "python3 -m"


def js_ladder(root, d, target):
    deps, _ = js_deps(d)
    x = js_runner(root, d)
    rel = "." if d == root else str(d.relative_to(root))
    out = []
    if "typescript" in deps and (d / "tsconfig.json").is_file():
        out.append((2, f"{x} tsc --noEmit -p {rel}/tsconfig.json --pretty false | grep -F -f .review/js.txt"
                       "   # весь проект, фильтр по своим файлам: tsc <files> игнорирует tsconfig"))
    if "eslint" in deps:
        out.append((2, f"xargs {x} eslint --max-warnings=0 --no-warn-ignored < .review/js.txt"
                       "   # включено ли правило: eslint --print-config <file>"))
    if "knip" in deps:
        out.append((2, f"{x} knip --reporter compact | grep -F -f .review/js.txt"))
    if "dependency-cruiser" in deps:
        out.append((2, f"{x} depcruise {rel}/src -T err-long" + (f" --affected {target}" if target else "")))
    if "size-limit" in deps:
        out.append((2, f"{x} size-limit --json   # на base и head, сравнить"))
    if "vitest" in deps:
        out.append((3, f"xargs {x} vitest related --run < .review/js.txt"))
    elif "jest" in deps:
        out.append((3, f"xargs {x} jest --ci --findRelatedTests < .review/js.txt"))
    if "@playwright/test" in deps and target:
        out.append((3, f"{x} playwright test --only-changed={target}"))
    return out


def py_ladder(root, d, stack):
    text = py_manifest_text(d) + read(d / "ruff.toml") + read(d / ".importlinter")
    r = py_runner(root, d)
    has = lambda name: re.search(rf"(?im)(^\[tool\.{name}\b|[\"']?\b{name}\b)", text)  # noqa: E731
    out = []
    if has("ruff") or (d / "ruff.toml").is_file():
        out.append((2, f"xargs {r} ruff check --output-format concise < .review/py.txt"))
    if has("mypy"):
        out.append((2, f"xargs {r} mypy < .review/py.txt 2>&1 | grep -F -f .review/py.txt"
                       "   # mypy идёт по импортам — оставить свои файлы"))
    if has("pyright"):
        out.append((2, f"xargs {r} pyright < .review/py.txt"))
    if has("importlinter") or has("import-linter") or (d / ".importlinter").is_file():
        out.append((2, f"{r} lint-imports"))
    if has("pytest"):
        debug = "PYTHONASYNCIODEBUG=1 " if stack == "python-fastapi" else ""
        out.append((3, f"{debug}{r} pytest -x -q -p no:cacheprovider tests/<area> -k <name>"
                       + ("   # 'took N seconds' = блокировка event loop" if debug else "")))
    return out


# ═══════════════════════════════════════════════════════════════
# the plan
# ═══════════════════════════════════════════════════════════════

def parse_stacks(value):
    if not value or value == "auto":
        return None
    names = [s.strip() for s in value.split(",") if s.strip()]
    unknown = [s for s in names if s not in STACKS]
    if unknown:
        raise ValueError("неизвестный стек: %s. Есть: %s" % (", ".join(unknown), ", ".join(STACKS)))
    return names


def write_file_lists(root, found):
    """.review/js.txt, .review/py.txt — the changed files per language, for xargs in the ladder."""
    review = root / ".review"
    review.mkdir(exist_ok=True)
    for lang in LANG_EXT:
        files = sorted({f for s, e in found.items() if STACKS[s]["lang"] == lang for f in e["files"]})
        if files:
            (review / f"{lang}.txt").write_text("\n".join(files) + "\n", encoding="utf-8")


def build(root, mode, stacks, target, write_lists=False):
    """(plan text, chosen stacks) — stacks=None means use the detected ones.

    write_lists: also write .review/js.txt and .review/py.txt (finding.py init does; show does not).
    """
    if mode not in MODES:
        raise ValueError("неизвестный режим: %s. Есть: %s" % (mode, ", ".join(MODES)))
    target = target or default_target(root)
    found, rules = detect(root, target)
    chosen = stacks or sorted(found)
    m = MODES[mode]
    lines = [f"Режим: {mode} — {m['title']}"]
    if not chosen:
        lines.append("Стек: не определён (нет диффа против цели и манифестов) — укажи --stack")
    for s in chosen:
        e = found.get(s, {"files": [], "dirs": {root}})
        where = ", ".join(sorted(str(d.relative_to(root)) if d != root else "." for d in e["dirs"]))
        lines.append(f"Стек: {s} — {STACKS[s]['title']} · изменённых файлов {len(e['files'])} · {where}")
    refs = list(m["refs"])
    for s in chosen:
        refs += STACKS[s]["refs"]
        for d in found.get(s, {"dirs": {root}})["dirs"]:
            deps, _ = js_deps(d) if STACKS[s]["lang"] == "js" else ({}, {})
            refs += [ref for dep, ref in STACKS[s].get("if_dep", {}).items() if dep in deps]
    refs = list(dict.fromkeys(refs))
    lines.append("Читать: " + ", ".join(refs))
    if rules:
        lines.append("Правила репо (их стайлгайд, выигрывают у публичных гайдов): " + ", ".join(rules))
    else:
        lines.append("Правила репо: не найдены — ссылаться на соседей (drift), не на вкус")
    ladder = []
    for s in chosen:
        for d in sorted(found.get(s, {"dirs": {root}})["dirs"]):
            ladder += (js_ladder(root, d, target) if STACKS[s]["lang"] == "js" else py_ladder(root, d, s))
    if ladder:
        lines.append("Лестница — команды этого репо (из корня, по спискам .review/js.txt и .review/py.txt):")
        lines += [f"  {rung}  {cmd}" for rung, cmd in dict.fromkeys(ladder)]
    else:
        lines.append("Лестница: инструментов репо не нашёл — ступень 2 из справочника стека, как зонд")
    lines.append(f"Фокус форм: {m['forms']}")
    lines.append(f"В MR не больше {m['max_nits']} nit; остальные — только в REVIEW-NOTES" if m["max_nits"]
                 else "nit в MR не идут — только в REVIEW-NOTES")
    if m["needs_requirements"]:
        lines.append("Гейт: render откажет без требований тикета — finding.py req --add \"<цитата>\"")
    if found and write_lists:
        write_file_lists(root, {s: e for s, e in found.items() if s in chosen})
    return "\n".join(lines), chosen


def main(argv=None):
    ap = argparse.ArgumentParser(description="review mode × stack → what to read and run")
    ap.add_argument("--dir", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("detect")
    q.add_argument("--target", default="")
    q.add_argument("--json", action="store_true")
    q = sub.add_parser("show")
    q.add_argument("--mode", default="full", choices=sorted(MODES))
    q.add_argument("--stack", default="auto", help="auto or comma list: " + ", ".join(STACKS))
    q.add_argument("--target", default="")
    a = ap.parse_args(argv)
    root = Path(a.dir).resolve()
    if a.cmd == "detect":
        found, rules = detect(root, a.target or default_target(root))
        if a.json:
            print(json.dumps({"stacks": {s: e["files"] for s, e in found.items()}, "rules": rules},
                             ensure_ascii=False, indent=2))
        else:
            for s, e in sorted(found.items()):
                print(f"{s}: {len(e['files'])} изменённых файлов — {STACKS[s]['title']}")
            print("правила репо: " + (", ".join(rules) or "—"))
        return 0
    try:
        text, _ = build(root, a.mode, parse_stacks(a.stack), a.target)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
