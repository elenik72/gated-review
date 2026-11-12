# Changelog

## 2.0.0 — 2026-11-12

A major version: a script or a bot that drives the gate has to change with it.

- **Breaking.** `render` refuses while a changed file is in no inventory entry; `render --json`
  no longer carries `resolve`; notes for the author are posted as one comment and reported as
  `note ok <location> comment=<id>`, not as threads; `add` and `fyi` refuse text GitLab would
  act on. Each is described below.
- Nothing GitLab would act on is posted. A comment goes out under the reviewer's own token, so a
  line that starts with a slash command (`/approve`, `/merge`) would run as that person and an
  `@name` outside code would notify them (`@all`: the whole project). `finding.py add` and `fyi`
  refuse such text, and `gitlab_comment.py` refuses it at the last door, for replies and
  questions too.
- `render` refuses while a changed file is in no inventory entry (a path, a glob, a directory, or
  a line that names the file); generated files do not count. The inventory was kept by component
  and read 99% «проверено» while reviews opened 40–78% of the files of a large MR.
  `cover --skip` adds the entry it skips, `cover --done` clears the reason.
- A large MR goes commit by commit: past 30 changed files the plan of `init` lists the commits
  with their files, `render --part "<which>"` closes one part without asking for the rest, and
  the last `render` asks for all of it.
- `finding.py drop --location … --why …` takes a recorded finding off: a repeat, or one a later
  check killed. It leaves the comments and stays on the notes page under «Сняты».
- Two rules in SKILL.md. What you could not read proves nothing: no finding rests on a page that
  did not open or a section cut off. When sources disagree, the weightiest decides: the
  specification a ticket points to outweighs the ticket's own criteria, the ticket outweighs a
  draft, a code comment or the MR description; code that follows the weightiest source is a note
  for the author, code that departs from it is a finding. Both came from one review that judged
  code by a specification cut in half.
- SKILL.md is 19,000 characters instead of 38,000: Claude Code keeps the first 5,000 tokens of a
  skill after a context compaction. The phases and the grading table moved to
  `reference/review-process.md` (the plan names it for every mode), the index of guides to
  `reference/guides.md`; `test_layout.py` keeps the size.
- Notes for the author are no longer threads. `post-batch` puts the notes of a review into one
  ordinary MR comment, each under a link to its line at the reviewed commit, and prints
  `note ok <location> comment=<id>` for each; `post` does the same for a single note. A thread
  failed either way: closed at posting, it was folded away before the author read it; open, it
  held the merge wherever the project requires every thread resolved, and nobody but the
  reviewer closed it (two approved merge requests waited eleven days on one note each). The
  script deletes the comment and exits non-zero if GitLab made it a thread. `threads` lists it
  as `comment`. `render --json` no longer carries `resolve`; `resolve --reopen` opens a thread
  again.
- `post` and `post-batch` anchor a comment on a line the change kept (context next to an edit) by
  its old number too, looked up in the MR's diff. GitLab refused such a comment with
  `line_code can't be blank`, and the batch stopped there.

## 1.3.0 — 2026-11-02

- Comment types. The header is `**[ai-review-bot]** · <тип> · <вес> · <вердикт>`: the type follows from
  the claim form the gate checked (🐞 Баг, 📋 Требование, 🔀 Коллизия, ⚠️ Риск, 📐 Единообразие), never from
  the model; the weight is one word («блокирует мерж», «желательно», «не важно») instead of the
  «Приоритет · Блокирующее» pair. `render --json` carries `kind`. A question's header is `· ❓ Вопрос`.
- Notes for the author: `finding.py fyi --location --source --text` — worth knowing, nothing to fix;
  a source is required, at most 240 characters and 3 per MR, no verdict or fix. `post-batch` posts them
  with the findings and closes their threads at once, so they never hold a merge.
- `collision`, `rule` and `unimplemented` may be blocking from rung 1: their refuting check is static
  and final. A review that may not run tests could not post a blocker at all before.
- `finding.py note` refuses a question to the author and points to `post --question`.
- Posting only on the reviewed head. `post` / `post-batch` refuse when the MR head is not the commit
  `init` recorded: GitLab anchors to the latest version, so after the author's push a comment landed on
  a line nobody checked, and the `DiffNote` check could not see it. `finding.py rehead --why` moves the
  review to the current HEAD after the findings were re-checked; the reason goes into the notes.
- Rules come from the target branch. The `rule` form quotes `--rule <file>:<lines>` as `origin/<target>`
  has it, so an MR that edits `AGENTS.md` is judged by the rule before the edit; a rule file the MR adds
  is refused. `init` without `--target` records the branch the plan falls back to (`origin/HEAD`). The
  plan says when the MR changes rule files, and SKILL.md states that text from the MR is data, not
  instructions to the reviewer.

## 1.2.1 — 2026-10-20

- `scripts/test_layout.py`: packaging checks that turn silent failures into test failures — the Claude
  Code and Codex manifests agree on name, version, description and license; every relative link and
  anchor in the skill resolves; every `scripts/*.py` the docs name ships and compiles; the frontmatter
  names the skill and its triggers.

## 1.2.0 — 2026-10-16

- No GitLab host is baked in: `gitlab_comment.py` takes `--host`, else `GITLAB_HOST`, else the host of
  `origin` of the repo under review, and refuses a `github.com` origin with a clear message.
- `finding.py init` adds `/.review/` and `/REVIEW-NOTES.md` to the local `.git/info/exclude` of the repo
  under review, so review state cannot be committed by accident.
- Codex manifests: `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`, next to the Claude
  Code ones; manifests carry `homepage` and `repository`.
- References inherited from awesome-skills/code-review-skill are fully in English (the Chinese parts are
  translated); table-of-contents anchors follow the new headings.
- README rewritten: what the author of an MR sees, how the gate works, how it is built (parts, review
  phases, finding types, what `render` checks), install for Claude Code and Codex.
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
