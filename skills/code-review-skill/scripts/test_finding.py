#!/usr/bin/env python3
"""Tests for finding.py (stdlib unittest, no extra deps).

The refusal paths are the point of the tool, so they carry most of the coverage:
a gate that can be talked past is a paragraph, not a gate.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from argparse import Namespace

import finding


def args(**over):
    """A finding that passes the gate, unless a field is overridden to break it."""
    base = dict(
        dir=".",
        form="breaks",
        claim="MediaTable падает на пустом списке",
        breaks_when="items = [] -> белый экран вместо пустого состояния",
        location="src/MediaTable.tsx:64",
        severity="blocking",
        rung=3,
        evidence="pnpm vitest run media.spec.ts",
        output="1 failed",
        sibling=None,
        assumption=None,
        fix=None,
    )
    base.update(over)
    return Namespace(**base)


# ═══════════════════════════════════════════════════════════════
# the gate — what it lets through
# ═══════════════════════════════════════════════════════════════

class GateAcceptsTest(unittest.TestCase):
    def test_evidence_gives_confirmed(self):
        f = finding.validate(args())
        self.assertEqual(f["verdict"], finding.CONFIRMED)
        self.assertEqual(f["location"], "src/MediaTable.tsx:64")

    def test_named_sibling_gives_confirmed(self):
        f = finding.validate(args(
            form="drift", severity="nit", rung=1,
            evidence=None, output=None, sibling="src/ChangeLogDialog.tsx:41",
        ))
        self.assertEqual(f["verdict"], finding.CONFIRMED)
        self.assertEqual(f["sibling"], "src/ChangeLogDialog.tsx:41")

    def test_assumption_gives_assumed(self):
        f = finding.validate(args(
            severity="important", rung=1, evidence=None, output=None,
            assumption="e2e-окружение не поднимается локально",
        ))
        self.assertEqual(f["verdict"], finding.ASSUMED)

    def test_unicode_arrow_is_accepted(self):
        f = finding.validate(args(breaks_when="items = [] → белый экран вместо пустого"))
        self.assertIn("→", f["breaks_when"])


# ═══════════════════════════════════════════════════════════════
# the gate — what it refuses
# ═══════════════════════════════════════════════════════════════

class GateRefusesTest(unittest.TestCase):
    def refusal(self, **over):
        with self.assertRaises(finding.Refused) as ctx:
            finding.validate(args(**over))
        return str(ctx.exception)

    def test_no_grounding_at_all(self):
        msg = self.refusal(evidence=None, output=None)
        self.assertIn("ни на чём не стоит", msg)

    def test_evidence_without_output_proves_nothing(self):
        msg = self.refusal(output=None)
        self.assertIn("--output", msg)

    def test_output_without_evidence(self):
        msg = self.refusal(evidence=None)
        self.assertIn("--output без --evidence", msg)

    def test_two_groundings_at_once(self):
        msg = self.refusal(sibling="src/Other.tsx:10")
        self.assertIn("несколько оснований", msg)

    def test_breaks_when_needs_an_observable_outcome(self):
        msg = self.refusal(breaks_when="может сломаться")
        self.assertIn("--breaks-when", msg)

    def test_breaks_when_too_short_even_with_arrow(self):
        msg = self.refusal(breaks_when="a -> b")
        self.assertIn("слишком короткий", msg)

    def test_location_must_name_a_line(self):
        msg = self.refusal(location="src/MediaTable.tsx")
        self.assertIn("точную строку", msg)

    def test_sibling_must_name_a_line(self):
        msg = self.refusal(form="drift", severity="nit", rung=1,
                           evidence=None, output=None, sibling="src/ChangeLogDialog.tsx")
        self.assertIn("--sibling", msg)

    def test_placeholder_claim(self):
        msg = self.refusal(claim="TODO")
        self.assertIn("--claim", msg)

    def test_unknown_form(self):
        msg = self.refusal(form="vibes")
        self.assertIn("неизвестная форма", msg)

    def test_drift_cannot_be_grounded_by_a_command(self):
        # convention drift is not executable — only a named sibling falsifies it
        msg = self.refusal(form="drift", severity="nit", rung=1)
        self.assertIn("--sibling", msg)

    def test_assumption_must_say_why(self):
        msg = self.refusal(severity="important", rung=1, evidence=None,
                           output=None, assumption="не смог")
        self.assertIn("--assumption", msg)


# ═══════════════════════════════════════════════════════════════
# severity is capped by the rung of evidence reached
# ═══════════════════════════════════════════════════════════════

class SeverityLadderTest(unittest.TestCase):
    def test_blocking_needs_more_than_reading_the_diff(self):
        with self.assertRaises(finding.Refused) as ctx:
            finding.validate(args(rung=0, severity="blocking",
                                  evidence="чтение диффа", output="строка 64"))
        self.assertIn("рунг 0", str(ctx.exception))

    def test_important_not_supported_by_rung_zero(self):
        with self.assertRaises(finding.Refused):
            finding.validate(args(rung=0, severity="important",
                                  evidence="чтение диффа", output="строка 64"))

    def test_grep_supports_important_but_not_blocking(self):
        finding.validate(args(rung=1, severity="important",
                              evidence="git grep MediaTable", output="3 hits"))
        with self.assertRaises(finding.Refused):
            finding.validate(args(rung=1, severity="blocking",
                                  evidence="git grep MediaTable", output="3 hits"))

    def test_running_tests_supports_blocking(self):
        f = finding.validate(args(rung=3, severity="blocking"))
        self.assertEqual(f["severity"], "blocking")

    def test_an_assumption_can_never_block_the_merge(self):
        with self.assertRaises(finding.Refused) as ctx:
            finding.validate(args(rung=5, severity="blocking", evidence=None,
                                  output=None, assumption="данные только в проде, локально не воспроизвести"))
        self.assertIn("предположение не может быть блокирующим", str(ctx.exception))

    def test_every_rung_has_a_cap(self):
        for rung in range(6):
            self.assertIn(rung, finding.RUNGS)


# ═══════════════════════════════════════════════════════════════
# rendering
# ═══════════════════════════════════════════════════════════════

class RenderTest(unittest.TestCase):
    def test_comment_header_matches_the_skill_format(self):
        body = finding.render_comment(finding.validate(args()))
        first = body.split("\n")[0]
        self.assertEqual(
            first,
            "**[ai-review-bot]** · 🐞 Баг · блокирует мерж · подтверждено",
        )

    def test_nit_is_non_blocking(self):
        body = finding.render_comment(finding.validate(
            args(severity="nit", rung=1, evidence="git grep", output="2 hits")))
        self.assertIn("· 🐞 Баг · не важно · подтверждено", body)
        self.assertNotIn("блокирует", body)

    def test_evidence_output_is_carried_into_the_comment(self):
        body = finding.render_comment(finding.validate(args(output="1 failed | 12 passed")))
        self.assertIn("1 failed | 12 passed", body)
        self.assertIn("pnpm vitest run media.spec.ts", body)

    def test_assumption_states_why(self):
        body = finding.render_comment(finding.validate(
            args(severity="important", rung=1, evidence=None, output=None,
                 assumption="e2e-окружение не поднимается локально")))
        self.assertIn("Почему это предположение", body)

    def test_ascii_arrow_is_normalised(self):
        body = finding.render_comment(finding.validate(args()))
        self.assertIn("→", body)
        self.assertNotIn("->", body)

    def test_blocking_findings_are_rendered_first(self):
        state = finding.blank_state()
        state["findings"] = [
            finding.validate(args(severity="nit", rung=1, evidence="git grep", output="2")),
            finding.validate(args(severity="blocking", rung=3)),
        ]
        out = finding.render_all(state)
        self.assertLess(out.index("🔴"), out.index("🟢"))

    def test_empty_review_says_so_plainly(self):
        self.assertIn("Ни одной находки", finding.render_all(finding.blank_state()))


class StatsTest(unittest.TestCase):
    def test_counts_confirmed_assumed_and_refuted(self):
        state = finding.blank_state()
        state["findings"] = [
            finding.validate(args(rung=3, severity="blocking")),
            finding.validate(args(severity="important", rung=1, evidence=None,
                                  output=None, assumption="данные только в продакшене")),
        ]
        state["refutations"] = [
            {"claim": "a", "killed_by": "b"},
            {"claim": "c", "killed_by": "d"},
            {"claim": "e", "killed_by": "f"},
        ]
        state["coverage"] = [
            {"path": "src/**", "done": True, "note": None},
            {"path": "db/**", "done": False, "note": "нет контекста"},
        ]
        block = finding.stats_block(state)
        self.assertIn("Проверено находок: 1", block)
        self.assertIn("Отброшено собственными проверками: 3", block)
        self.assertIn("Осталось предположениями: 1", block)
        self.assertIn("Не осмотрено: `db/**`", block)

    def test_notes_page_has_all_five_sections(self):
        page = finding.render_notes(finding.blank_state())
        for section in ("## Проверено", "## Предполагается", "## Опровергнуто",
                        "## Покрытие", "## План"):
            self.assertIn(section, page)


# ═══════════════════════════════════════════════════════════════
# cli round-trip
# ═══════════════════════════════════════════════════════════════

class TypesAndNotesTest(unittest.TestCase):
    """The type comes from the form; notes for the author are short, sourced and capped."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.cli("init")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def cli(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return finding.main(["--dir", self.root] + list(argv))

    def fyi(self, text="MR !1972 удаляет этот же ключ, порядок мержа важен", source="!1972",
            location="src/a.ts:12"):
        return self.cli("fyi", "--location", location, "--text", text, "--source", source)

    def collision(self, **over):
        return args(form="collision", severity="important", rung=1,
                    evidence="git grep -l row origin/b", output="src/b.scss", **over)

    def test_every_form_has_a_type(self):
        self.assertEqual(set(finding.KINDS), set(finding.CLAIM_FORMS))

    def test_header_names_the_type_from_the_form(self):
        body = finding.render_comment(finding.validate(self.collision()))
        self.assertEqual(body.split("\n")[0],
                         "**[ai-review-bot]** · 🔀 Коллизия · желательно · подтверждено")

    def test_static_forms_may_block_on_reading_the_code(self):
        f = finding.validate(args(form="collision", severity="blocking", rung=1,
                                  evidence="git grep -l row origin/b", output="src/b.scss"))
        self.assertEqual(f["severity"], "blocking")
        with self.assertRaises(finding.Refused):  # behaviour still needs a test run
            finding.validate(args(form="breaks", severity="blocking", rung=1,
                                  evidence="git grep -n items", output="src/a.ts:3"))
        with self.assertRaises(finding.Refused):  # reading the diff alone still caps
            finding.validate(args(form="collision", severity="blocking", rung=0,
                                  evidence="git diff", output="src/a.scss"))

    def test_render_json_carries_the_type_notes_last(self):
        self.cli("cover", "--add", "src/**")
        self.assertEqual(self.cli(
            "add", "--form", "collision", "--severity", "important", "--rung", "1",
            "--claim", "класс .row объявлен и в ветке b",
            "--breaks-when", "обе ветки в main -> таблица свёрстана чужими стилями",
            "--location", "src/a.scss:3", "--evidence", "git grep -l row origin/b",
            "--output", "src/b.scss"), 0)
        self.assertEqual(self.fyi(), 0)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            finding.main(["--dir", self.root, "render", "--json"])
        items = json.loads(out.getvalue())
        self.assertEqual([i["kind"] for i in items], ["collision", "note"])
        self.assertEqual((items[1]["severity"], items[1]["verdict"]), ("note", ""))
        self.assertTrue(items[1]["body"].startswith(finding.FYI_HEAD))

    def test_fyi_refuses_what_is_not_a_note(self):
        for bad in (dict(source=""), dict(location="src/a.ts"), dict(text="x" * 300),
                    dict(text="Стоит уточнить у автора, согласованы ли имена"),
                    dict(text="Почему здесь не общий хук?"),
                    dict(text="Ломается при пустом списке, белый экран")):
            self.assertEqual(self.fyi(**bad), 2, bad)
        for _ in range(5):  # as many as the review has to say
            self.assertEqual(self.fyi(), 0)

    def test_note_refuses_a_question_to_the_author(self):
        self.assertEqual(self.cli("note", "Вопрос автору: пустая строка в eventVariables подставляется"), 2)
        self.assertEqual(self.cli("note", "Тикет просил согласовать имена, стоит подтвердить в треде"), 2)
        self.assertEqual(self.cli("note", "Вопрос аналитику о D-152 остаётся открытым"), 0)

    def test_notes_page_lists_notes_for_the_author(self):
        self.fyi()
        page = open(os.path.join(self.root, finding.NOTES_FILE), encoding="utf-8").read()
        self.assertIn("## Заметки для автора (1)", page)


class HideFromGitTest(unittest.TestCase):
    """Review state must not end up in a commit of the repo under review."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        subprocess.run(["git", "init", "-q", self.root], check=True)
        self.exclude = os.path.join(self.root, ".git", "info", "exclude")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_init_excludes_state_once_and_keeps_existing_lines(self):
        with open(self.exclude, "w", encoding="utf-8") as fh:
            fh.write("*.log")  # no trailing newline on purpose
        finding.hide_from_git(self.root)
        finding.hide_from_git(self.root)
        lines = open(self.exclude, encoding="utf-8").read().splitlines()
        self.assertEqual(lines, ["*.log", "/.review/", "/REVIEW-NOTES.md"])

    def test_state_files_are_untracked_by_git(self):
        os.makedirs(os.path.join(self.root, ".review"))
        open(os.path.join(self.root, ".review", "state.json"), "w").close()
        open(os.path.join(self.root, "REVIEW-NOTES.md"), "w").close()
        finding.hide_from_git(self.root)
        status = subprocess.run(["git", "-C", self.root, "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        self.assertEqual(status, "")

    def test_outside_git_does_nothing(self):
        plain = tempfile.mkdtemp()
        try:
            finding.hide_from_git(plain)
        finally:
            shutil.rmtree(plain, ignore_errors=True)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_cli(self, *argv):
        # the CLI reports to stdout; keep the test output readable
        with contextlib.redirect_stdout(io.StringIO()):
            return finding.main(["--dir", self.root] + list(argv))

    def test_init_creates_state_and_notes(self):
        self.assertEqual(self.run_cli("init", "--target", "main"), 0)
        self.assertTrue(os.path.exists(finding.state_path(self.root)))
        self.assertTrue(os.path.exists(os.path.join(self.root, finding.NOTES_FILE)))

    def test_add_without_init_is_refused(self):
        self.assertEqual(self.run_cli(
            "add", "--form", "breaks", "--claim", "x",
            "--breaks-when", "items = [] -> белый экран вместо пустого",
            "--location", "a.ts:1", "--severity", "nit", "--rung", "1",
            "--evidence", "git grep", "--output", "2"), 2)

    def test_refusal_exits_with_two(self):
        self.run_cli("init")
        code = self.run_cli(
            "add", "--form", "breaks", "--claim", "x",
            "--breaks-when", "items = [] -> белый экран вместо пустого",
            "--location", "a.ts:1", "--severity", "blocking", "--rung", "0",
            "--evidence", "чтение диффа", "--output", "строка 1")
        self.assertEqual(code, 2)

    def test_accepted_finding_reaches_state_and_notes(self):
        self.run_cli("init")
        self.assertEqual(self.run_cli(
            "add", "--form", "breaks", "--claim", "падает на пустом списке",
            "--breaks-when", "items = [] -> белый экран вместо пустого состояния",
            "--location", "src/MediaTable.tsx:64", "--severity", "blocking", "--rung", "3",
            "--evidence", "pnpm vitest run", "--output", "1 failed"), 0)

        with open(finding.state_path(self.root), encoding="utf-8") as fh:
            state = json.load(fh)
        self.assertEqual(len(state["findings"]), 1)

        with open(os.path.join(self.root, finding.NOTES_FILE), encoding="utf-8") as fh:
            page = fh.read()
        self.assertIn("падает на пустом списке", page)
        self.assertIn("Проверено находок: 1", page)

    def test_refute_lands_in_the_notes(self):
        self.run_cli("init")
        self.assertEqual(self.run_cli(
            "refute", "--claim", "formatSize не обрабатывает 0",
            "--killed-by", "utils/format.ts:12 — есть ветка if (!n)"), 0)
        with open(os.path.join(self.root, finding.NOTES_FILE), encoding="utf-8") as fh:
            page = fh.read()
        self.assertIn("Думал: formatSize не обрабатывает 0", page)

    def test_refute_without_a_killer_is_refused(self):
        self.run_cli("init")
        self.assertEqual(self.run_cli("refute", "--claim", "x", "--killed-by", "нет"), 2)

    def test_coverage_marks_carry_into_stats(self):
        self.run_cli("init")
        self.run_cli("cover", "--add", "src/**", "db/**")
        self.run_cli("cover", "--done", "src/**")
        with open(os.path.join(self.root, finding.NOTES_FILE), encoding="utf-8") as fh:
            page = fh.read()
        self.assertIn("- [x] src/**", page)
        self.assertIn("- [ ] db/**", page)
        self.assertIn("Не осмотрено: `db/**`", page)

    def test_init_twice_needs_force(self):
        self.run_cli("init")
        self.assertEqual(self.run_cli("init"), 2)
        self.assertEqual(self.run_cli("init", "--force"), 0)

    def test_force_init_archives_previous_state(self):
        self.run_cli("init", "--pr", "!1")
        self.run_cli("init", "--force")
        archive = os.path.join(self.root, finding.STATE_DIR, "archive")
        self.assertEqual(len(os.listdir(archive)), 1)

    def test_render_warns_when_head_moved(self):
        self.run_cli("init")
        self.run_cli("cover", "--add", "src/**")
        with open(finding.state_path(self.root), encoding="utf-8") as fh:
            state = json.load(fh)
        state["head"] = "0000000"
        finding.save_state(self.root, state)
        real = finding.git_head
        finding.git_head = lambda root: "1111111"
        try:
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                self.assertEqual(finding.main(["--dir", self.root, "render"]), 0)
        finally:
            finding.git_head = real
        self.assertIn("могли съехать", err.getvalue())

    def test_rehead_needs_a_reason_and_moves_the_review(self):
        self.run_cli("init")
        state = finding.load_state(self.root)
        state["head"] = "0000000"
        finding.save_state(self.root, state)
        real = finding.git_head
        finding.git_head = lambda root: "1111111"
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(self.run_cli("rehead", "--why", "ок"), 2)
            self.assertEqual(self.run_cli("rehead", "--why", "перепроверил 1 находку: строки не съехали"), 0)
        finally:
            finding.git_head = real
        state = finding.load_state(self.root)
        self.assertEqual(state["head"], "1111111")
        self.assertIn("Ревью перенесено с 0000000 на 1111111", state["notes"][-1])

    def test_render_silent_when_head_unknown(self):
        # a state written by an older version has no "head" — no warning, no crash
        self.run_cli("init")
        self.run_cli("cover", "--add", "src/**")
        with open(finding.state_path(self.root), encoding="utf-8") as fh:
            state = json.load(fh)
        state.pop("head", None)
        finding.save_state(self.root, state)
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(finding.main(["--dir", self.root, "render"]), 0)
        self.assertEqual(err.getvalue(), "")


    def test_render_without_inventory_is_refused(self):
        # Phase 0.4 skipped: nothing would tell the reader what was never examined
        self.run_cli("init")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_cli("render"), 2)

    def test_no_inventory_reason_goes_into_the_phase_4_block(self):
        self.run_cli("init")
        self.assertEqual(self.run_cli("render", "--no-inventory", "PR из двух файлов, прочитан целиком"), 0)
        block = finding.stats_block(finding.load_state(self.root))
        self.assertIn("Инвентарь покрытия не составлялся: PR из двух файлов", block)
        self.assertEqual(self.run_cli("render"), 0)  # the reason is remembered


class ModesAndRequirementsTest(unittest.TestCase):
    """Mode × stack, the ticket's requirements, repo rules, and the nit budget."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        with open(os.path.join(self.root, "AGENTS.md"), "w", encoding="utf-8") as fh:
            fh.write("# Rules\n- Сервисы не импортируют роутеры.\n\n- Деньги — только Decimal.\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def cli(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = finding.main(["--dir", self.root] + list(argv))
        return code, err.getvalue()

    def add(self, *extra, **over):
        base = {"--form": "breaks", "--severity": "nit", "--rung": "1",
                "--claim": "формат суммы расходится с соседним экраном",
                "--breaks-when": "сумма 1000 -> в отчёте 1000.0 вместо 1 000",
                "--location": "src/a.ts:%d" % over.pop("line", 3),
                "--evidence": "git grep -n formatMoney", "--output": "src/b.ts:4 formatMoney(x)"}
        base.update({"--" + k.replace("_", "-"): v for k, v in over.items()})
        argv = ["add"] + [x for kv in base.items() for x in kv if kv[1] is not None] + list(extra)
        return self.cli(*argv)[0]

    def test_rule_form_quotes_the_rule_it_cites(self):
        self.cli("init")
        self.assertEqual(self.add(**{"form": "rule", "evidence": None, "output": None,
                                     "rule": "AGENTS.md:2"}), 0)
        f = finding.load_state(self.root)["findings"][0]
        self.assertEqual(f["verdict"], finding.CONFIRMED)
        self.assertIn("«- Сервисы не импортируют роутеры.»", finding.render_comment(f))

    def test_rule_citations_must_point_at_real_text(self):
        self.cli("init")
        for rule in ("NOPE.md:1", "AGENTS.md:40", "AGENTS.md:3"):   # no file, past the end, empty line
            self.assertEqual(self.add(**{"form": "rule", "evidence": None, "output": None, "rule": rule}), 2, rule)
        self.assertEqual(self.add(**{"form": "rule"}), 2)                        # rule form needs --rule
        self.assertEqual(self.add(**{"evidence": None, "output": None, "rule": "AGENTS.md:2"}), 2)

    def test_business_mode_needs_the_ticket(self):
        self.cli("init", "--mode", "business")
        self.cli("cover", "--add", "src/**")
        self.assertEqual(self.cli("render")[0], 2)                               # nothing to compare with
        self.cli("req", "--add", "открытие нового оверлея закрывает предыдущий", "--source", "SPH-1")
        self.assertEqual(self.cli("render")[0], 2)                               # R1 has no status
        self.assertEqual(self.cli("req", "--mark", "R1", "--status", "met", "--where", "src/a.ts:3")[0], 2)
        self.assertEqual(self.cli("req", "--mark", "R1", "--status", "met", "--where", "src/a.ts:3",
                                  "--evidence", "pnpm vitest run overlay", "--output", "3 passed")[0], 0)
        self.assertEqual(self.cli("render")[0], 0)
        self.assertIn("полностью соответствует", finding.stats_block(finding.load_state(self.root)))

    def test_no_ticket_is_said_out_loud(self):
        self.cli("init", "--mode", "business")
        self.cli("cover", "--add", "src/**")
        self.assertEqual(self.cli("render", "--no-ticket", "тикета нет, задача поставлена устно")[0], 0)
        self.assertIn("не сверялись: тикета нет", finding.stats_block(finding.load_state(self.root)))

    def test_missing_requirement_needs_proof_of_absence(self):
        self.cli("init")
        self.cli("req", "--add", "пустой список показывает пустое состояние")
        self.assertEqual(self.cli("req", "--mark", "R1", "--status", "missing")[0], 2)
        self.assertEqual(self.cli("req", "--mark", "R1", "--status", "missing",
                                  "--evidence", "git grep -n EmptyState src/media", "--output", "(пусто)")[0], 0)

    def test_compliance_is_computed_not_judged(self):
        met, miss, unv = ({"status": "met"}, {"status": "missing"}, {"status": "unverified"})
        self.assertEqual(finding.compliance([met, met]), "полностью соответствует")
        self.assertEqual(finding.compliance([met, miss]), "частично соответствует")
        self.assertEqual(finding.compliance([miss]), "не соответствует")
        self.assertEqual(finding.compliance([met, unv]), "код соответствует, нужна проверка человеком")
        self.assertIn("без статуса", finding.compliance([met, {"status": None}]))

    def test_every_minor_finding_is_rendered_in_any_mode(self):
        self.cli("init", "--mode", "business")
        self.cli("cover", "--add", "src/**")
        self.cli("render", "--no-ticket", "проверка без лимита")
        self.add()
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            finding.main(["--dir", self.root, "render", "--json"])
        self.assertEqual(len(json.loads(out.getvalue())), 1)

        self.cli("init", "--force")
        self.cli("cover", "--add", "src/**")
        for line in range(1, 8):
            self.add(line=line)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            finding.main(["--dir", self.root, "render", "--json"])
        self.assertEqual(len(json.loads(out.getvalue())), 7)

    def test_init_keeps_the_plan_for_after_a_compaction(self):
        self.assertEqual(self.cli("init", "--mode", "design", "--stack", "python-fastapi")[0], 0)
        state = finding.load_state(self.root)
        self.assertEqual((state["mode"], state["stacks"]), ("design", ["python-fastapi"]))
        with open(os.path.join(self.root, finding.NOTES_FILE), encoding="utf-8") as fh:
            self.assertIn("reference/python-fastapi.md", fh.read())
        self.assertEqual(self.cli("init", "--force", "--stack", "ruby")[0], 2)


class RuleFromTargetTest(unittest.TestCase):
    """The MR under review may edit AGENTS.md; it is judged by the rule its target branch has."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.git("init", "-q", "-b", "main")
        self.write("AGENTS.md", "# Rules\n- Сервисы не импортируют роутеры.\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")
        self.git("checkout", "-qb", "feature")
        self.write("AGENTS.md", "# Rules\n- Сервисам можно всё.\n")
        self.write("NEW.md", "# New\n- Новое правило из этого MR.\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "change the rules")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def git(self, *argv):
        subprocess.run(["git", "-C", self.root, "-c", "user.email=t@t", "-c", "user.name=t", *argv],
                       check=True, capture_output=True)

    def write(self, name, text):
        with open(os.path.join(self.root, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def add_rule(self, rule):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = finding.main(["--dir", self.root, "add", "--form", "rule", "--severity", "nit",
                                 "--rung", "1", "--claim", "сервис импортирует роутер",
                                 "--breaks-when", "app/pay.py:3 импортирует app.api -> цикл импортов",
                                 "--location", "app/pay.py:3", "--rule", rule])
        return code, err.getvalue()

    def init(self, target):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(finding.main(["--dir", self.root, "init", "--target", target]), 0)

    def test_the_rule_is_quoted_from_the_target_branch(self):
        self.init("main")
        self.assertEqual(self.add_rule("AGENTS.md:2")[0], 0)
        body = finding.render_comment(finding.load_state(self.root)["findings"][0])
        self.assertIn("Сервисы не импортируют роутеры", body)
        self.assertNotIn("можно всё", body)

    def test_a_rule_the_mr_adds_is_not_a_rule_yet(self):
        self.init("main")
        code, err = self.add_rule("NEW.md:2")
        self.assertEqual(code, 2)
        self.assertIn("добавляет сам MR", err)

    def test_init_without_a_target_reads_rules_from_the_plans_default(self):
        self.git("update-ref", "refs/remotes/origin/main", "main")
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(finding.main(["--dir", self.root, "init"]), 0)
        self.assertEqual(finding.load_state(self.root)["target"], "origin/main")

    def test_an_unreadable_target_is_refused(self):
        self.init("nope")
        code, err = self.add_rule("AGENTS.md:2")
        self.assertEqual(code, 2)
        self.assertIn("не читается", err)


class ShapeTest(unittest.TestCase):
    """A comment is read between the author's lines: one claim, short steps, the proof folded."""

    def refused(self, **over):
        with self.assertRaises(finding.Refused) as ctx:
            finding.validate(args(**over))
        return str(ctx.exception)

    def test_a_paragraph_claim_is_refused(self):
        msg = self.refused(claim="Описание закрывает задачу словом Closes, а её runtime-часть не сделана: "
                                 "карточка по снимку Run и подпись события Failed в журнале; сама задача говорит, "
                                 "что после раннего результата она не считается завершённой.")
        self.assertIn("finding.py note", msg)

    def test_more_than_three_steps_is_a_task_not_a_comment(self):
        self.assertIn("задача", self.refused(fix=["шаг 1", "шаг 2", "шаг 3", "шаг 4"]))

    def test_a_list_of_places_is_not_a_command(self):
        self.refused(evidence="; ".join(["Block 6 «HTTP read model»", "TActivityEntityDto в api/dto.ts",
                                         "activities.change_log.events в en.yml", "ChangeLog/Entry.tsx:30",
                                         "merged_at MR vs resolutiondate задач"]))

    def test_output_lines_must_fit_the_screen(self):
        self.refused(output="Block 6: GET .../activities/{id} отдаёт " + "readOnly, players, " * 10)
        self.refused(output="\n".join("line %d" % n for n in range(12)))

    def test_steps_render_as_a_list_and_the_proof_is_folded(self):
        body = finding.render_comment(finding.validate(args(fix=["заменить Closes на Relates to",
                                                                 "закрыть задачу тем MR, что переключит API"])))
        self.assertIn("**Что сделать:**\n- заменить Closes на Relates to\n- закрыть", body)
        self.assertIn("<details><summary>Как проверено</summary>", body)
        self.assertLess(body.index("Что сделать"), body.index("Как проверено"))

    def test_an_old_state_with_a_single_fix_string_still_renders(self):
        f = finding.validate(args())
        f["fix"] = "один шаг строкой, как в старом state.json"
        self.assertIn("**Что сделать:** один шаг строкой", finding.render_comment(f))


# ═══════════════════════════════════════════════════════════════
# what GitLab would act on, every changed file accounted for, taking a finding off
# ═══════════════════════════════════════════════════════════════

class UnsafeTextTest(unittest.TestCase):
    def test_a_line_that_starts_with_a_slash_command_is_named(self):
        self.assertIn("/approve", finding.unsafe("код читается так:\n/approve\nи всё"))
        self.assertIn("/merge", finding.unsafe("```\nвывод\n```\n```\n  /merge when ready"))

    def test_paths_and_comments_are_not_commands(self):
        for text in ("/usr/bin/env python3", "// комментарий", "см. src/a.ts и /api/v1/users", "делим a / b"):
            self.assertIsNone(finding.unsafe(text), text)

    def test_a_mention_outside_code_is_named_and_inside_code_is_not(self):
        self.assertIn("@all", finding.unsafe("нужно согласовать, @all"))
        self.assertIn("@nestjs", finding.unsafe("обновлён @nestjs/axios"))
        for text in ("декоратор `@Injectable()`", "```\n@media (max-width: 1px)\n```", "пишите на a@b.example"):
            self.assertIsNone(finding.unsafe(text), text)

    def test_the_gate_refuses_a_finding_gitlab_would_run(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            finding.main(["--dir", root, "init"])
            code = finding.main([
                "--dir", root, "add", "--form", "breaks", "--claim", "падает на пустом списке",
                "--breaks-when", "items = [] -> белый экран вместо пустого состояния",
                "--location", "src/MediaTable.tsx:64", "--severity", "nit", "--rung", "1",
                "--evidence", "git grep", "--output", "/approve"])
        self.assertEqual(code, 2)


class ChangedFilesTest(unittest.TestCase):
    """render wants every changed file in the inventory: looked at, or skipped out loud."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "T")
        self.write("README.md")
        self.git("commit", "-q", "-m", "base")
        self.git("checkout", "-q", "-b", "feature")
        self.write("src/a.ts", "src/b.ts", "spec/a.spec.ts", "yarn.lock")
        self.git("commit", "-q", "-m", "change")
        self.cli("init", "--target", "main")

    def git(self, *argv):
        subprocess.run(["git", "-C", self.root, *argv], check=True, capture_output=True)

    def write(self, *names):
        for name in names:
            path = os.path.join(self.root, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(name + "\n")
        self.git("add", ".")

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = finding.main(["--dir", self.root] + list(argv))
        return code, out.getvalue() + err.getvalue()

    def test_a_changed_file_outside_the_inventory_stops_render(self):
        self.cli("cover", "--add", "src/a.ts")
        code, said = self.cli("render")
        self.assertEqual(code, 2)
        self.assertIn("src/b.ts", said)
        self.assertIn("spec/a.spec.ts", said)
        self.assertNotIn("yarn.lock", said)  # generated: nobody reads it

    def test_a_glob_a_directory_and_a_skip_all_account_for_files(self):
        self.cli("cover", "--add", "src/*.ts")
        self.cli("cover", "--skip", "spec/", "--why", "тесты не смотрел")
        code, said = self.cli("render")
        self.assertEqual(code, 0, said)
        with open(os.path.join(self.root, finding.NOTES_FILE), encoding="utf-8") as page:
            self.assertIn("тесты не смотрел", page.read())

    def test_one_part_of_a_review_in_parts_may_leave_the_rest(self):
        self.cli("cover", "--add", "src/a.ts")
        self.assertEqual(self.cli("render", "--part", "первый коммит")[0], 0)
        self.assertEqual(self.cli("render")[0], 2)

    def test_done_clears_the_reason_a_file_was_skipped_for(self):
        self.cli("cover", "--skip", "src/a.ts", "--why", "позже")
        _, said = self.cli("cover", "--done", "src/a.ts")
        self.assertIn("[x] src/a.ts\n", said)


class DropTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.cli("init")
        self.cli("add", "--form", "breaks", "--claim", "падает на пустом списке",
                 "--breaks-when", "items = [] -> белый экран вместо пустого состояния",
                 "--location", "src/MediaTable.tsx:64", "--severity", "nit", "--rung", "1",
                 "--evidence", "git grep", "--output", "2 вызова")

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = finding.main(["--dir", self.root] + list(argv))
        return code, out.getvalue() + err.getvalue()

    def test_a_dropped_finding_leaves_the_comments_and_stays_on_the_notes_page(self):
        code, _ = self.cli("drop", "--location", "src/MediaTable.tsx:64", "--why", "повтор находки на строке 12")
        self.assertEqual(code, 0)
        state = finding.load_state(self.root)
        self.assertEqual(state["findings"], [])
        self.assertEqual(state["dropped"][0]["why"], "повтор находки на строке 12")
        with open(os.path.join(self.root, finding.NOTES_FILE), encoding="utf-8") as page:
            self.assertIn("Снято: повтор находки на строке 12", page.read())

    def test_dropping_needs_a_reason_and_an_existing_finding(self):
        self.assertEqual(self.cli("drop", "--location", "src/Other.tsx:1", "--why", "повтор")[0], 2)
        self.assertEqual(self.cli("drop", "--location", "src/MediaTable.tsx:64", "--why", " ")[0], 2)


if __name__ == '__main__':
    unittest.main()
