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
            "**[ai-review-bot]** · Приоритет: важно · Блокирующее: да · подтверждено",
        )

    def test_nit_is_non_blocking(self):
        body = finding.render_comment(finding.validate(
            args(severity="nit", rung=1, evidence="git grep", output="2 hits")))
        self.assertIn("Приоритет: не важно · Блокирующее: нет", body)

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

    def test_nit_budget_follows_the_mode(self):
        self.cli("init", "--mode", "business")
        self.cli("cover", "--add", "src/**")
        self.cli("render", "--no-ticket", "проверка лимита nit")
        self.add()
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            finding.main(["--dir", self.root, "render", "--json"])
        self.assertEqual(json.loads(out.getvalue()), [])                         # business: no nits in the MR

        self.cli("init", "--force")                                              # full: at most five
        self.cli("cover", "--add", "src/**")
        for line in range(1, 8):
            self.add(line=line)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            finding.main(["--dir", self.root, "render", "--json"])
        self.assertEqual(len(json.loads(out.getvalue())), 5)

    def test_init_keeps_the_plan_for_after_a_compaction(self):
        self.assertEqual(self.cli("init", "--mode", "design", "--stack", "python-fastapi")[0], 0)
        state = finding.load_state(self.root)
        self.assertEqual((state["mode"], state["stacks"]), ("design", ["python-fastapi"]))
        with open(os.path.join(self.root, finding.NOTES_FILE), encoding="utf-8") as fh:
            self.assertIn("reference/python-fastapi.md", fh.read())
        self.assertEqual(self.cli("init", "--force", "--stack", "ruby")[0], 2)


if __name__ == '__main__':
    unittest.main()
