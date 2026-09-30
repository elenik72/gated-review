#!/usr/bin/env python3
"""
finding.py — the gate that a code-review finding has to pass before it becomes a comment.

The paid action in a review is the posted comment. Everything else — grep, the
type-checker, one test run — is free. This tool refuses to accept a finding that did not
survive a check, and the refusal costs nothing. See "The Gate" in SKILL.md.

A finding is accepted only if it carries all of:

  * a claim in one of the known forms              (--form / --claim)
  * a failure scenario with an observable outcome  (--breaks-when "<state> -> <what breaks>")
  * an exact anchor for the inline comment         (--location path/File.ts:64)
  * one of three kinds of grounding:
        --evidence "<cmd>" --output "<what it printed>"   -> подтверждено
        --sibling path/Sibling.tsx:41                     -> подтверждено (non-executable form)
        --rule AGENTS.md:12-14                            -> подтверждено (form "rule": the lines are read and quoted)
        --assumption "<why it could not be checked>"      -> предположение
  * a severity the evidence actually supports      (--severity / --rung)

Typical session:

    python scripts/finding.py init --target origin/main --mode business --stack auto   # prints the plan
    python scripts/finding.py req --add "открытие нового оверлея закрывает предыдущий" --source "SPH-1 AC2"
    python scripts/finding.py add --form breaks --severity blocking --rung 3 \\
        --claim "MediaTable падает на пустом списке" \\
        --breaks-when "items = [] -> белый экран вместо пустого состояния" \\
        --location src/features/media/MediaTable.tsx:64 \\
        --evidence "pnpm vitest run media.spec.ts" --output "1 failed"
    python scripts/finding.py refute --claim "formatSize не обрабатывает 0" \\
        --killed-by "utils/format.ts:12 — есть ветка if (!n)"
    python scripts/finding.py cover --add "src/**"   # render refuses without an inventory
    python scripts/finding.py render
    python scripts/finding.py stats

State lives in .review/state.json; REVIEW-NOTES.md is regenerated from it after every
change, so the notes page is never out of date with the findings.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_plan  # noqa: E402  — the mode × stack registry

STATE_DIR = ".review"
STATE_FILE = "state.json"
NOTES_FILE = "REVIEW-NOTES.md"

CONFIRMED = "подтверждено"
ASSUMED = "предположение"

# severity: rank is compared against the cap the evidence ladder allows
SEVERITIES = {
    "blocking": {"icon": "🔴", "prio": "важно", "blocks": "да", "rank": 3},
    "important": {"icon": "🟡", "prio": "желательно", "blocks": "нет", "rank": 2},
    "nit": {"icon": "🟢", "prio": "не важно", "blocks": "нет", "rank": 1},
}

# rung -> (what you did, highest severity rank it supports)
RUNGS = {
    0: ("прочитал diff", 1),
    1: ("git grep по репозиторию и соседним веткам, прочитал соседей", 2),
    2: ("типы / линт / сборка по изменённым файлам", 2),
    3: ("прогнал существующие тесты по этому пути", 3),
    4: ("написал падающий тест или мини-воспроизведение", 3),
    5: ("запустил приложение", 3),
}

# form -> (how the claim reads, whether a named sibling is the only valid grounding)
CLAIM_FORMS = {
    "breaks": ("ломается при", False),
    "unimplemented": ("требование не реализовано", False),
    "collision": ("коллизия идентификатора с соседней веткой", False),
    "drift": ("расходится с соседями", True),
    "unread": ("возвращаемое значение никто не читает", False),
    "invariant": ("инвариант не закреплён и ломается", False),
    "rule": ("нарушает правило самого репо", False),
    "unrequested": ("поведение, которого не требует тикет", False),
}
RULE_RE = re.compile(r"^(?P<path>[^\s:]+):(?P<a>\d+)(?:-(?P<b>\d+))?$")
REQ_STATUSES = {
    "met": ("✅", "выполнено"),
    "partial": ("⚠️", "частично"),
    "missing": ("❌", "не выполнено"),
    "unverified": ("👀", "нужна проверка человеком"),
}

LOCATION_RE = re.compile(r"^[^\s:]+:\d+$")
ARROW_RE = re.compile(r"(->|→)")

PLACEHOLDERS = ("todo", "tbd", "xxx", "fixme", "...", "[описание]", "[description]")


class Refused(Exception):
    """The gate said no. Refusing is free; posting an unverified claim is not."""


# ═══════════════════════════════════════════════════════════════
# state
# ═══════════════════════════════════════════════════════════════

def state_path(root):
    return os.path.join(root, STATE_DIR, STATE_FILE)


def blank_state():
    return {
        "created": date.today().isoformat(),
        "target": None,
        "pr": None,
        "head": None,
        "findings": [],
        "refutations": [],
        "coverage": [],
        "plan": [],
        "notes": [],
        "mode": "full",
        "stacks": [],
        "requirements": [],
    }


def git_head(root):
    """Short HEAD sha of the reviewed working copy, or None outside git."""
    try:
        out = subprocess.run(
            ["git", "-C", root, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except OSError:
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def load_state(root):
    path = state_path(root)
    if not os.path.exists(path):
        raise Refused(
            "нет %s — сначала `finding.py init`.\n"
            "Заметки и находки живут в одном месте, чтобы после сжатия контекста\n"
            "review можно было продолжить с того же места." % path
        )
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_state(root, state):
    os.makedirs(os.path.join(root, STATE_DIR), exist_ok=True)
    with open(state_path(root), "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


# ═══════════════════════════════════════════════════════════════
# the gate
# ═══════════════════════════════════════════════════════════════

def looks_like_placeholder(text):
    low = text.strip().lower()
    return any(low == p or low.startswith(p) for p in PLACEHOLDERS)


def read_rule(root, rule):
    """The quoted lines of a repo rule, or Refused: a citation must point at real text."""
    m = RULE_RE.match(rule or "")
    if not m:
        raise Refused("--rule должен быть <файл>:<строка> или <файл>:<с>-<по>, получено %r" % rule)
    a, b = int(m.group("a")), int(m.group("b") or m.group("a"))
    path = os.path.join(root, m.group("path"))
    if not os.path.isfile(path):
        raise Refused("файла правила нет: %s. Ссылаться можно только на правило, которое есть в репо." % path)
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    if not 1 <= a <= b <= len(lines) or b - a > 30:
        raise Refused("строк %d-%d в %s нет (в файле %d строк) или диапазон длиннее 30 строк."
                      % (a, b, m.group("path"), len(lines)))
    quote = " ".join(l.strip() for l in lines[a - 1:b] if l.strip())
    if not quote:
        raise Refused("в %s пусто — процитировать нечего." % rule)
    return quote[:300]


def compliance(reqs):
    """The compliance level is computed here, not judged by the model (as PR-Agent does)."""
    if not reqs:
        return None
    count = {k: sum(1 for r in reqs if r.get("status") == k) for k in REQ_STATUSES}
    unmarked = sum(1 for r in reqs if not r.get("status"))
    if unmarked:
        return "не оценено: %d требований без статуса" % unmarked
    if count["missing"] or count["partial"]:
        return "частично соответствует" if count["met"] else "не соответствует"
    if count["unverified"]:
        return "код соответствует, нужна проверка человеком"
    return "полностью соответствует"


def validate(args):
    """Return a finding dict, or raise Refused with what is missing and why it matters."""
    if args.form not in CLAIM_FORMS:
        raise Refused(
            "неизвестная форма утверждения %r.\n"
            "Допустимы только эти, и у каждой есть проверка, которая её опровергает:\n%s"
            % (args.form, "\n".join("  %-14s %s" % (k, v[0]) for k, v in CLAIM_FORMS.items()))
        )

    if not args.claim or looks_like_placeholder(args.claim):
        raise Refused("--claim пустой или заглушка. Утверждение должно быть таким, "
                      "чтобы репозиторий мог его опровергнуть.")

    if not ARROW_RE.search(args.breaks_when or ""):
        raise Refused(
            "--breaks-when должен иметь вид «<вход / состояние> -> <что увидит пользователь>».\n"
            "Получено: %r\n"
            "Без наблюдаемого следствия это не находка, а впечатление: автору нечего\n"
            "воспроизвести и нечего проверить после исправления." % (args.breaks_when or "")
        )

    if len(args.breaks_when.strip()) < 20:
        raise Refused("--breaks-when слишком короткий, чтобы что-то значить: %r" % args.breaks_when)

    if not LOCATION_RE.match(args.location or ""):
        raise Refused(
            "--location должен указывать точную строку: path/File.tsx:64, получено %r.\n"
            "Комментарий вешается на строку диффа, а не на страницу PR целиком." % (args.location or "")
        )

    if args.rung not in RUNGS:
        raise Refused("--rung должен быть 0..5, получено %r" % args.rung)

    if args.severity not in SEVERITIES:
        raise Refused("--severity должен быть blocking | important | nit, получено %r" % args.severity)

    # exactly one grounding
    rule = getattr(args, "rule", None)
    modes = [
        bool(args.evidence or args.output),
        bool(args.sibling),
        bool(rule),
        bool(args.assumption),
    ]
    if sum(modes) == 0:
        raise Refused(
            "находка ни на чём не стоит. Нужно ровно одно из:\n"
            "  --evidence \"<команда>\" --output \"<что она напечатала>\"  -> подтверждено\n"
            "  --sibling path/Sibling.tsx:41                           -> подтверждено\n"
            "  --rule AGENTS.md:12-14   (только для формы rule)        -> подтверждено\n"
            "  --assumption \"<почему проверить не удалось>\"             -> предположение\n"
            "Репозиторий — бесплатный оракул: почти всё можно попытаться убить до публикации."
        )
    if sum(modes) > 1:
        raise Refused("указано несколько оснований сразу — выбери одно: evidence, sibling, rule или assumption.")
    if args.form == "rule" and not rule:
        raise Refused(
            "форма rule опирается на правило самого репо — нужен --rule <файл>:<строки>.\n"
            "«Так не принято» без строки правила — это вкус; со строкой — факт, который автор проверит.")
    if rule and args.form != "rule":
        raise Refused("--rule — основание только для формы rule; для остальных — evidence или sibling.")
    rule_quote = read_rule(args.dir, rule) if rule else None

    verdict = ASSUMED if args.assumption else CONFIRMED

    if args.evidence or args.output:
        if not args.evidence:
            raise Refused("--output без --evidence: не видно, какая команда это напечатала.")
        if not (args.output or "").strip():
            raise Refused(
                "--evidence без --output. Команда, вывод которой не приложен, ничего не доказывает —\n"
                "и автор не сможет повторить проверку."
            )

    is_sibling_only = CLAIM_FORMS[args.form][1]
    if is_sibling_only and not args.sibling:
        raise Refused(
            "форма %r не проверяется исполнением — её опровергает названный сосед.\n"
            "Нужен --sibling path/Sibling.tsx:41. «Расходится с остальным модулем» —\n"
            "это спорно; «X и Y принимают dataCy пропсом, этот зашивает» — нет."
            % args.form
        )

    if args.sibling and not LOCATION_RE.match(args.sibling):
        raise Refused("--sibling должен быть path/File.tsx:41, получено %r" % args.sibling)

    if args.assumption and len(args.assumption.strip()) < 15:
        raise Refused(
            "--assumption должен объяснять, почему проверка не сделана "
            "(нет тестового окружения, данные только в проде, соседняя ветка не выкачана). "
            "Получено: %r" % args.assumption
        )

    # severity vs the ladder
    cap_rank = RUNGS[args.rung][1]
    want_rank = SEVERITIES[args.severity]["rank"]
    if want_rank > cap_rank:
        allowed = [k for k, v in SEVERITIES.items() if v["rank"] <= cap_rank]
        raise Refused(
            "серьёзность %s не опирается на рунг %d (%s).\n"
            "На этом рунге максимум: %s.\n"
            "Либо поднимись по лестнице доказательств, либо ставь ниже и скажи вслух,\n"
            "почему подтвердить не вышло." % (
                SEVERITIES[args.severity]["icon"] + " " + args.severity,
                args.rung, RUNGS[args.rung][0],
                ", ".join(sorted(allowed, key=lambda k: -SEVERITIES[k]["rank"])),
            )
        )

    if verdict == ASSUMED and args.severity == "blocking":
        raise Refused(
            "предположение не может быть блокирующим. Если оно того стоит — проверь его "
            "(рунг 3+); если проверить нечем, ставь important и скажи, чего не хватило."
        )

    return {
        "form": args.form,
        "claim": args.claim.strip(),
        "breaks_when": args.breaks_when.strip(),
        "location": args.location,
        "severity": args.severity,
        "rung": args.rung,
        "evidence": args.evidence,
        "output": (args.output or "").strip() or None,
        "sibling": args.sibling,
        "rule": rule,
        "rule_quote": rule_quote,
        "assumption": args.assumption,
        "fix": args.fix,
        "verdict": verdict,
    }


# ═══════════════════════════════════════════════════════════════
# rendering
# ═══════════════════════════════════════════════════════════════

def render_comment(f):
    """The inline comment exactly as SKILL.md specifies it."""
    sev = SEVERITIES[f["severity"]]
    head = "**[ai-review-bot]** · Приоритет: %s · Блокирующее: %s · %s" % (
        sev["prio"], sev["blocks"], f["verdict"],
    )
    breaks = f["breaks_when"].replace("->", "→")
    parts = [head, "", f["claim"], "", "**Ломается при:** %s" % breaks]

    if f.get("evidence"):
        parts += ["", "**Проверка:** `%s`" % f["evidence"], "", "```", f["output"] or "", "```"]
    elif f.get("sibling"):
        parts += ["", "**Сосед для сравнения:** `%s`" % f["sibling"]]
    elif f.get("rule"):
        parts += ["", "**Правило репо:** `%s` — «%s»" % (f["rule"], f["rule_quote"])]
    if f.get("assumption"):
        parts += ["", "**Почему это предположение:** %s" % f["assumption"]]
    if f.get("fix"):
        parts += ["", "**Что сделать:** %s" % f["fix"]]
    return "\n".join(parts)


def render_all(state, as_json=False):
    findings = state["findings"]
    if as_json:
        return json.dumps(
            [{"location": f["location"], "severity": f["severity"],
              "verdict": f["verdict"], "body": render_comment(f)} for f in findings],
            ensure_ascii=False, indent=2,
        )
    if not findings:
        return "Ни одной находки не прошло шлюз. Это нормальный исход — значит, ревью не нашло того,\nчто пережило бы проверку."
    out = []
    order = {"blocking": 0, "important": 1, "nit": 2}
    for n, f in enumerate(sorted(findings, key=lambda x: order[x["severity"]]), 1):
        out.append("─" * 72)
        out.append("#%d  %s  %s" % (n, SEVERITIES[f["severity"]]["icon"], f["location"]))
        out.append("─" * 72)
        out.append(render_comment(f))
        out.append("")
    return "\n".join(out)


def render_notes(state):
    confirmed = [f for f in state["findings"] if f["verdict"] == CONFIRMED]
    assumed = [f for f in state["findings"] if f["verdict"] == ASSUMED]

    L = ["# Review notes", ""]
    if state.get("target") or state.get("pr"):
        L += ["Цель мержа: `%s`  ·  PR: %s" % (state.get("target") or "?", state.get("pr") or "—"), ""]
    L += ["> Одна страница. Переписывается по ходу, а не в конце. После сжатия контекста",
          "> читать этот файл первым и продолжать с раздела «План».",
          "> Сгенерировано `scripts/finding.py` — правь через него, чтобы не разошлось.", ""]

    if state.get("plan_text"):
        L += ["## Как ревьюить", "", "```text", state["plan_text"], "```", ""]
    if state.get("requirements"):
        L += ["## Требования тикета", ""] + requirement_rows(state["requirements"]) + [""]

    L += ["## Проверено", ""]
    if confirmed:
        for f in confirmed:
            ground = ("`%s` → %s" % (f["evidence"], (f["output"] or "").replace("\n", " ")[:80])
                      if f.get("evidence") else "сосед `%s`" % f["sibling"] if f.get("sibling")
                      else "правило `%s`" % f.get("rule"))
            L.append("- %s `%s` — %s. Проверка: %s. **%s**, рунг %d." % (
                SEVERITIES[f["severity"]]["icon"], f["location"], f["claim"], ground,
                f["verdict"], f["rung"]))
    else:
        L.append("_пусто_")

    L += ["", "## Предполагается", ""]
    if assumed:
        for f in assumed:
            L.append("- %s `%s` — %s. Не проверено: %s" % (
                SEVERITIES[f["severity"]]["icon"], f["location"], f["claim"], f["assumption"]))
    else:
        L.append("_пусто_")

    L += ["", "## Опровергнуто", ""]
    if state["refutations"]:
        for r in state["refutations"]:
            L.append("- Думал: %s → %s" % (r["claim"], r["killed_by"]))
    else:
        L.append("_пусто — если здесь пусто на середине большого PR, скорее всего гипотезы\n"
                 "не проверялись, а отбрасывались молча._")

    L += ["", "## Покрытие", ""]
    if state["coverage"]:
        for c in state["coverage"]:
            L.append("- [%s] %s%s" % ("x" if c["done"] else " ", c["path"],
                                      " — %s" % c["note"] if c.get("note") else ""))
    else:
        L.append("_пусто — инвентарь из Phase 0.4 сюда_")

    L += ["", "## План", ""]
    if state["plan"]:
        for p in state["plan"]:
            L.append("- [%s] %s" % ("x" if p["done"] else " ", p["text"]))
    else:
        L.append("_пусто_")

    if state["notes"]:
        L += ["", "## Заметки", ""] + ["- %s" % n for n in state["notes"]]

    L += ["", "---", "", stats_block(state)]
    return "\n".join(L) + "\n"


def requirement_rows(reqs):
    rows = ["| ID | Требование (цитата) | Статус | Где / почему |", "|---|---|---|---|"]
    for r in reqs:
        icon, word = REQ_STATUSES.get(r.get("status"), ("…", "без статуса"))
        parts = [p for p in (r.get("where"), r.get("why")) if p]
        if r.get("evidence"):
            parts.append("`%s` → %s" % (r["evidence"], (r.get("output") or "").replace("\n", " ")[:60]))
        where = " · ".join(parts)
        rows.append("| %s | «%s»%s | %s %s | %s |" % (
            r["id"], r["quote"].replace("|", "/"), " (%s)" % r["source"] if r.get("source") else "",
            icon, word, where.replace("|", "/") or "—"))
    return rows


def stats_block(state):
    confirmed = sum(1 for f in state["findings"] if f["verdict"] == CONFIRMED)
    assumed = sum(1 for f in state["findings"] if f["verdict"] == ASSUMED)
    done = [c["path"] for c in state["coverage"] if c["done"]]
    left = [c["path"] for c in state["coverage"] if not c["done"]]
    return "\n".join([
        "## Для Phase 4",
        "",
        "> Проверено находок: %d. Отброшено собственными проверками: %d. "
        "Осталось предположениями: %d." % (confirmed, len(state["refutations"]), assumed),
        "> Осмотрено: %s. Не осмотрено: %s." % (
            ", ".join("`%s`" % p for p in done) or "—",
            ", ".join("`%s`" % p for p in left) or "—",
        ) if state["coverage"] or not state.get("no_inventory") else
        "> Инвентарь покрытия не составлялся: %s." % state["no_inventory"],
    ] + requirements_block(state))


def requirements_block(state):
    reqs = state.get("requirements") or []
    if not reqs:
        return (["", "> Требования тикета не сверялись: %s." % state["no_ticket"]]
                if state.get("no_ticket") else [])
    n = {k: sum(1 for r in reqs if r.get("status") == k) for k in REQ_STATUSES}
    return ["", "> Требования: выполнено %d, частично %d, не выполнено %d, нужна проверка человеком %d "
            "— **%s**." % (n["met"], n["partial"], n["missing"], n["unverified"], compliance(reqs)),
            ""] + requirement_rows(reqs)


def write_notes(root, state):
    with open(os.path.join(root, NOTES_FILE), "w", encoding="utf-8") as fh:
        fh.write(render_notes(state))


# ═══════════════════════════════════════════════════════════════
# commands
# ═══════════════════════════════════════════════════════════════

def cmd_init(args):
    root = args.dir
    if os.path.exists(state_path(root)):
        if not args.force:
            raise Refused(
                "%s уже существует — продолжай текущее ревью или начни новое через --force\n"
                "(старое состояние не пропадёт: уедет в %s/archive/)."
                % (state_path(root), STATE_DIR))
        archive_dir = os.path.join(root, STATE_DIR, "archive")
        os.makedirs(archive_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        archived = os.path.join(archive_dir, "state-%s.json" % stamp)
        shutil.move(state_path(root), archived)
        print("прошлое ревью убрано в %s" % archived)
    state = blank_state()
    state["target"] = args.target
    state["pr"] = args.pr
    state["head"] = git_head(root)
    state["mode"] = args.mode
    try:
        text, stacks = review_plan.build(
            review_plan.Path(root).resolve(), args.mode, review_plan.parse_stacks(args.stack),
            args.target or "", write_lists=True)
    except ValueError as exc:
        raise Refused(str(exc))
    state["stacks"], state["plan_text"] = stacks, text
    save_state(root, state)
    write_notes(root, state)
    print("создано: %s и %s\n" % (state_path(root), os.path.join(root, NOTES_FILE)))
    print(text)
    return 0


def cmd_add(args):
    state = load_state(args.dir)
    finding = validate(args)
    state["findings"].append(finding)
    save_state(args.dir, state)
    write_notes(args.dir, state)
    sev = SEVERITIES[finding["severity"]]
    print("принято: %s %s %s (%s, рунг %d)" % (
        sev["icon"], finding["location"], finding["claim"], finding["verdict"], finding["rung"]))
    return 0


def cmd_refute(args):
    state = load_state(args.dir)
    if len((args.killed_by or "").strip()) < 10:
        raise Refused("--killed-by должен называть, что именно убило гипотезу "
                      "(файл:строка или команда с выводом).")
    state["refutations"].append({"claim": args.claim.strip(), "killed_by": args.killed_by.strip()})
    save_state(args.dir, state)
    write_notes(args.dir, state)
    print("записано в «Опровергнуто»: %s" % args.claim)
    return 0


def cmd_cover(args):
    state = load_state(args.dir)
    if args.add:
        for path in args.add:
            if not any(c["path"] == path for c in state["coverage"]):
                state["coverage"].append({"path": path, "done": False, "note": None})
    if args.done:
        for path in args.done:
            hit = [c for c in state["coverage"] if c["path"] == path]
            if not hit:
                raise Refused("нет такого пункта покрытия: %s" % path)
            hit[0]["done"] = True
    if args.skip:
        for path in args.skip:
            hit = [c for c in state["coverage"] if c["path"] == path]
            if not hit:
                raise Refused("нет такого пункта покрытия: %s" % path)
            hit[0]["note"] = args.why or "не смотрел"
    save_state(args.dir, state)
    write_notes(args.dir, state)
    for c in state["coverage"]:
        print("[%s] %s%s" % ("x" if c["done"] else " ", c["path"],
                             " — %s" % c["note"] if c.get("note") else ""))
    return 0


def cmd_plan(args):
    state = load_state(args.dir)
    if args.add:
        for text in args.add:
            state["plan"].append({"text": text, "done": False})
    if args.done is not None:
        if not 1 <= args.done <= len(state["plan"]):
            raise Refused("нет пункта плана №%d" % args.done)
        state["plan"][args.done - 1]["done"] = True
    save_state(args.dir, state)
    write_notes(args.dir, state)
    for n, p in enumerate(state["plan"], 1):
        print("%d. [%s] %s" % (n, "x" if p["done"] else " ", p["text"]))
    return 0


def cmd_note(args):
    state = load_state(args.dir)
    state["notes"].append(args.text)
    save_state(args.dir, state)
    write_notes(args.dir, state)
    print("записано")
    return 0


def cmd_req(args):
    """The ticket's requirements, quoted, each with a status that is grounded like a finding."""
    state = load_state(args.dir)
    reqs = state.setdefault("requirements", [])
    for quote in args.add or []:
        if len(quote.strip()) < 10 or looks_like_placeholder(quote):
            raise Refused("требование — дословная цитата из тикета, а не пересказ: %r" % quote)
        reqs.append({"id": "R%d" % (len(reqs) + 1), "quote": quote.strip(), "source": args.source,
                     "status": None})
    if args.mark:
        hit = [r for r in reqs if r["id"] == args.mark.upper()]
        if not hit:
            raise Refused("нет требования %s — есть: %s" % (args.mark, ", ".join(r["id"] for r in reqs) or "—"))
        r, st = hit[0], args.status
        if st not in REQ_STATUSES:
            raise Refused("--status: %s" % " | ".join(REQ_STATUSES))
        if st in ("met", "partial") and not LOCATION_RE.match(args.where or ""):
            raise Refused("%s: нужен --where path/File.ts:64 — где это реализовано." % st)
        if st == "met" and not (args.evidence and (args.output or "").strip()):
            raise Refused("met: нужна проверка, которая могла бы это опровергнуть — "
                          "--evidence \"<тест или grep>\" --output \"<что напечатал>\".")
        if st == "partial" and len((args.why or "").strip()) < 10:
            raise Refused("partial: --why — чего именно не хватает.")
        if st == "missing" and not (args.evidence and (args.output or "").strip()):
            raise Refused("missing: покажи отсутствие — --evidence \"git grep -n <что должно быть>\" "
                          "--output \"<пусто или где нашлось не то>\".")
        if st == "unverified" and len((args.why or "").strip()) < 10:
            raise Refused("unverified: --why — почему по коду не проверить (стенд, данные, UI).")
        r.update(status=st, where=args.where, evidence=args.evidence,
                 output=(args.output or "").strip() or None, why=(args.why or "").strip() or None)
    save_state(args.dir, state)
    write_notes(args.dir, state)
    for line in requirement_rows(reqs):
        print(line)
    level = compliance(reqs)
    if level:
        print("\nуровень: %s" % level)
    return 0


def cmd_render(args):
    state = load_state(args.dir)
    if args.no_inventory:
        state["no_inventory"] = args.no_inventory.strip()
        save_state(args.dir, state)
        write_notes(args.dir, state)
    mode = review_plan.MODES.get(state.get("mode") or "full", review_plan.MODES["full"])
    if args.no_ticket:
        state["no_ticket"] = args.no_ticket.strip()
        save_state(args.dir, state)
        write_notes(args.dir, state)
    reqs = state.get("requirements") or []
    if mode["needs_requirements"] and not reqs and not state.get("no_ticket"):
        raise Refused(
            "режим business без требований: сверять не с чем.\n"
            "Процитируй тикет — finding.py req --add \"<дословное требование>\" --source \"<KEY>\".\n"
            "Одно описание PR требованием не считается. Тикета нет совсем — скажи это:\n"
            "  finding.py render --no-ticket \"тикета нет, автор описал задачу устно\"")
    unmarked = [r["id"] for r in reqs if not r.get("status")]
    if unmarked:
        raise Refused("у требований нет статуса: %s — finding.py req --mark <ID> --status …"
                      % ", ".join(unmarked))
    if not state["coverage"] and not state.get("no_inventory"):
        raise Refused(
            "инвентарь покрытия пуст — Phase 0.4 не сделана.\n"
            "Без него сводка Phase 4 не может сказать, что осталось непросмотренным, и ревью,\n"
            "покрывшее треть PR, читается как одобрение всего. Составь его:\n"
            "  finding.py cover --add <пути или glob'ы>   (потом --done / --skip по мере чтения)\n"
            "или, если инвентарь здесь не нужен, скажи почему — это попадёт в сводку:\n"
            "  finding.py render --no-inventory \"PR из двух файлов, прочитан целиком\"")
    head_then, head_now = state.get("head"), git_head(args.dir)
    if head_then and head_now and head_then != head_now:
        print(
            "ВНИМАНИЕ: находки записаны на HEAD %s, сейчас HEAD %s — номера строк могли съехать.\n"
            "Перепроверь --location каждой находки по текущему диффу перед постингом."
            % (head_then, head_now),
            file=sys.stderr)
    nits = [f for f in state["findings"] if f["severity"] == "nit"]
    dropped = nits[mode["max_nits"]:]
    if dropped:
        state = dict(state, findings=[f for f in state["findings"] if f not in dropped])
        print("ещё %d nit не идут в MR (лимит режима — %d): они остаются в REVIEW-NOTES."
              % (len(dropped), mode["max_nits"]), file=sys.stderr)
    print(render_all(state, as_json=args.json))
    return 0


def cmd_stats(args):
    print(stats_block(load_state(args.dir)))
    return 0


def cmd_notes(args):
    state = load_state(args.dir)
    write_notes(args.dir, state)
    print(render_notes(state))
    return 0


# ═══════════════════════════════════════════════════════════════
# cli
# ═══════════════════════════════════════════════════════════════

def build_parser():
    p = argparse.ArgumentParser(
        prog="finding.py",
        description="The gate a review finding passes before it becomes a comment.",
    )
    p.add_argument("--dir", default=".", help="where .review/ and REVIEW-NOTES.md live (default: .)")
    sub = p.add_subparsers(dest="cmd")

    q = sub.add_parser("init", help="start a review")
    q.add_argument("--target", help="branch this PR merges into")
    q.add_argument("--pr", help="PR/MR reference")
    q.add_argument("--mode", default="full", choices=sorted(review_plan.MODES),
                   help="what the review is for; see review_plan.py")
    q.add_argument("--stack", default="auto", help="auto or a comma list: " + ", ".join(review_plan.STACKS))
    q.add_argument("--force", action="store_true")
    q.set_defaults(func=cmd_init)

    q = sub.add_parser("add", help="submit a finding to the gate")
    q.add_argument("--form", required=True, choices=sorted(CLAIM_FORMS))
    q.add_argument("--claim", required=True, help="the falsifiable claim, one line")
    q.add_argument("--breaks-when", required=True,
                   help='"<вход / состояние> -> <что увидит пользователь>"')
    q.add_argument("--location", required=True, help="path/File.tsx:64 — the line to anchor on")
    q.add_argument("--severity", required=True, choices=sorted(SEVERITIES))
    q.add_argument("--rung", required=True, type=int, help="0..5, see the evidence ladder")
    q.add_argument("--evidence", help="the command that could have killed this claim")
    q.add_argument("--output", help="what that command printed")
    q.add_argument("--sibling", help="path/Sibling.tsx:41 — for claims nothing executes")
    q.add_argument("--rule", help="AGENTS.md:12-14 — the repo rule a 'rule' finding violates")
    q.add_argument("--assumption", help="why the claim could not be checked -> предположение")
    q.add_argument("--fix", help="what to do about it")
    q.set_defaults(func=cmd_add)

    q = sub.add_parser("refute", help="record a hypothesis your own check killed")
    q.add_argument("--claim", required=True)
    q.add_argument("--killed-by", required=True, help="file:line or command + output")
    q.set_defaults(func=cmd_refute)

    q = sub.add_parser("cover", help="the Phase 0.4 inventory")
    q.add_argument("--add", nargs="+")
    q.add_argument("--done", nargs="+")
    q.add_argument("--skip", nargs="+", help="mark as deliberately not examined")
    q.add_argument("--why", help="reason used by --skip")
    q.set_defaults(func=cmd_cover)

    q = sub.add_parser("req", help="the ticket's requirements and their status")
    q.add_argument("--add", action="append", metavar="QUOTE", help="a requirement quoted from the ticket")
    q.add_argument("--source", help="ticket key / section the quotes come from")
    q.add_argument("--mark", metavar="ID", help="R1, R2 …")
    q.add_argument("--status", choices=sorted(REQ_STATUSES))
    q.add_argument("--where", help="path/File.ts:64")
    q.add_argument("--evidence")
    q.add_argument("--output")
    q.add_argument("--why")
    q.set_defaults(func=cmd_req)

    q = sub.add_parser("plan", help="what is left to do")
    q.add_argument("--add", nargs="+")
    q.add_argument("--done", type=int, metavar="N")
    q.set_defaults(func=cmd_plan)

    q = sub.add_parser("note", help="free-form line for the notes page")
    q.add_argument("text")
    q.set_defaults(func=cmd_note)

    q = sub.add_parser("render", help="print the comments, ready to post")
    q.add_argument("--json", action="store_true",
                   help="structured output; gitlab_comment.py post-batch --input takes it as is")
    q.add_argument("--no-inventory", metavar="WHY",
                   help="render without a Phase 0.4 inventory; the reason goes into the Phase 4 block")
    q.add_argument("--no-ticket", metavar="WHY",
                   help="business mode without a ticket; the reason goes into the Phase 4 block")
    q.set_defaults(func=cmd_render)

    q = sub.add_parser("stats", help="the Phase 4 coverage block")
    q.set_defaults(func=cmd_stats)

    q = sub.add_parser("notes", help="regenerate and print REVIEW-NOTES.md")
    q.set_defaults(func=cmd_notes)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except Refused as exc:
        print("ОТКАЗАНО\n\n%s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
