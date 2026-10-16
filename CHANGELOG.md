# Changelog

## 1.2.0 — 2026-10-16

- No GitLab host is baked in: `gitlab_comment.py` takes `--host`, else `GITLAB_HOST`, else the host of
  `origin` of the repo under review, and refuses a `github.com` origin with a clear message.
- `finding.py init` adds `/.review/` and `/REVIEW-NOTES.md` to the local `.git/info/exclude` of the repo
  under review, so review state cannot be committed by accident.
- Codex manifests: `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`, next to the Claude
  Code ones; manifests carry `homepage` and `repository`.
- References inherited from awesome-skills/code-review-skill are fully in English (the Chinese parts are
  translated); table-of-contents anchors follow the new headings.
- README rewritten: what the author of an MR sees, how the gate works, install for Claude Code and Codex.
- Fixed: the link from `reference/posting.md` to the posting script; the right edge of the error-hierarchy
  diagram.

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
