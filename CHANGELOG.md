# Changelog

## 1.1.0 — 2026-10-01

- Comments are scannable: `finding.py add` caps each field (claim 160, scenario 240, up to 3 fix steps of
  160, proof 10×120 characters) and refuses an `--evidence` that is a list of places, not a command;
  `--fix` repeats and renders as a list; the command and its output fold under «Как проверено».
- SKILL.md no longer asks for long explanations; context (what is already done, what is not needed, plans
  for other MRs) goes to `finding.py note`, not into a comment. Before/after example in SKILL.md.
- Questions (`post --question`) and replies (`reply`) must carry the `[ai-review-bot]` tag.

## 1.0.0 — 2026-09-30

- Packaged as a Claude Code plugin + marketplace (`.claude-plugin/`), readable by Codex; `agents/openai.yaml`.
- Review modes `full | business | design | security` and stacks `ts-react | node-nestjs | typescript |
  python-fastapi | python`, detected from the diff; `review_plan.py` prints what to read and the repo's own
  ladder commands; `finding.py init --mode --stack` stores the choice, REVIEW-NOTES repeats the plan.
- Business mode: quoted ticket requirements (`finding.py req`), statuses with evidence, compliance level
  computed by the script; `render` refuses without requirements (`--no-ticket` to say why).
- New claim forms: `rule` (cites and quotes a repo rule, `--rule file:lines`) and `unrequested`.
- Nit budget per mode in `render`; posting refuses any body that did not pass the gate.
- References: Python and FastAPI; React SPA checks (React Compiler, Rules of React lint, TanStack keys,
  a11y, forms, knip, dependency-cruiser); business-logic and design review; posting moved out of SKILL.md.
- Fixed teaching-bug examples: `useOptimistic` outside an Action, Server Action without authz/validation,
  promise created in client render, `exports` with `types` last, `baseUrl`; ladder rung 2 runs `tsc -p`.
- Evals for `claude plugin eval`: planted bug, clean MR, missing ticket requirement.
