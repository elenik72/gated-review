---
name: code-review-skill
description: |
  Evidence-gated code review for TypeScript/React 19 (Vite SPA), Node.js/NestJS and Python/FastAPI,
  with selectable modes: business (does the change implement the ticket's requirements correctly),
  design (style guide, architecture and code design by the repo's own rules), security, or full.
  A finding becomes a comment only after a check failed to kill it; comments go inline to the exact
  diff line of a GitLab MR in the [ai-review-bot] format (priority, blocking, verdict).
  ALWAYS invoke this skill when asked to review an MR/PR, post or reply to review comments, or
  resolve review threads. Use when: reviewing pull requests, code review, reviewing code changes,
  checking an MR against its Jira ticket, business-logic review, architecture review, style-guide
  review, security audit, performance review, posting review findings to an MR, replying in review
  discussions, re-review after fixes.
  Russian triggers: «проведи ревью», «сделай ревью MR», «проверь по тикету», «ревью бизнес-логики»,
  «ревью по стайлгайду», «архитектурное ревью», «отпиши в МРе», «оставь комментарии в MR»,
  «ответь на комментарии ревью», «зарезолвь ветки».
argument-hint: "[full|business|design|security] [ts-react|node-nestjs|python-fastapi|auto] [!MR | ticket]"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git *)      # diffs, call sites, sibling branches
  - Bash(python3 *)  # the gate, the plan, posting — other tools ask first
  - WebFetch         # current documentation
---

# Code Review Skill

## Start here — choose how to review

Arguments: `$ARGUMENTS`

The scripts live in `${CLAUDE_SKILL_DIR}/scripts/` (in Codex and in the reference files: `<skill>/scripts/`,
the directory of this SKILL.md). Run them from the root of the repository under review.

1. **Mode and stack.** Take them from the arguments when given. Otherwise detect the stack first —
   `python3 ${CLAUDE_SKILL_DIR}/scripts/review_plan.py detect --target origin/<target>` — then ask
   **one** `AskUserQuestion` (in Codex: one plain message with the same options and defaults):
   - *mode* — `business` (Recommended when the MR links a ticket) · `design` · `security` · `full`
     (Recommended otherwise). Each option's description says what it checks: business = the ticket's
     requirements are implemented and the business rules are right; design = the repo's style rules,
     architecture boundaries and code design; security = injections, access, secrets; full = all.
   - *stack* — the detected stacks as the recommended answer, multiSelect.
2. **Start the review** — this prints the plan: what to read, which repo files are the style guide,
   the ladder commands for this repo, the mode's gates:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/finding.py init --target origin/<target> --pr "!<iid>" \
     --mode <mode> --stack <stack|auto>
   ```

   Read the references the plan lists — not all of them, not others. `REVIEW-NOTES.md` repeats the plan
   under «Как ревьюить»: after a context compaction, read that file first.
3. **Business mode:** quote each requirement of the ticket with `finding.py req --add`; `render` refuses
   while there are none or one has no status ([business-logic-review.md](reference/business-logic-review.md)).
   **Design mode:** a finding against a written repo rule uses the `rule` form with `--rule <file>:<lines>`
   ([design-review.md](reference/design-review.md)).
4. Then Phase 0 → 4 below, with the gate on every finding.

## Core Principles

Review goals, tone, prioritization and the anti-patterns on both sides live in
[Code Review Best Practices](reference/code-review-best-practices.md). Read it once; it is
not repeated here. What follows is not advice but mechanism.

**Never reviewed by hand:** formatting, import order, lint violations, simple typos. Those
belong to Prettier / `ruff format` / black and the linter, and a comment about them spends the author's attention
on something a tool already owns.

## The Gate — a finding becomes a comment only after a check failed to kill it

The **paid action in a review is the posted comment.** It spends the author's attention and
the reviewer's credibility, and it cannot be taken back. Everything else — `grep`, opening
the neighbouring file, the type-checker, one targeted test run — is free: it runs against a
repository that is already there and costs nobody anything.

That asymmetry is the whole method. **The repository is a free oracle, so there is no
excuse for posting an unverified claim.** Before a finding may be written as a comment:

1. It is stated as a **falsifiable claim** — one of the forms below, phrased so that
   something in the repository could contradict it.
2. A **check that could have killed it was run and did not** — and its output goes in the
   comment. For the forms where nothing is executable, a **concrete sibling is named**
   (`path/File.tsx:NN`), never "the rest of the module".
3. It carries a **verdict** — подтверждено or предположение.

A finding that passes none of these is not a finding. Turn it into a question to the author
— a cheap form that claims nothing — or drop it. There is no third option in which an
impression is posted as a fact.

**Run the gate, do not just believe it.** [`scripts/finding.py`](scripts/finding.py) refuses
a finding that is missing any of the three, and refusing is free:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/finding.py init --target origin/main --pr "!482" --mode full

python3 ${CLAUDE_SKILL_DIR}/scripts/finding.py add --form breaks --severity blocking --rung 3 \
  --claim "MediaTable падает на пустом списке" \
  --breaks-when "items = [] -> белый экран вместо пустого состояния" \
  --location src/features/media/MediaTable.tsx:64 \
  --evidence "pnpm vitest run media.spec.ts" --output "1 failed | 12 passed"

python3 ${CLAUDE_SKILL_DIR}/scripts/finding.py refute --claim "formatSize не обрабатывает 0" \
  --killed-by "utils/format.ts:12 — есть ветка if (!n)"

python3 ${CLAUDE_SKILL_DIR}/scripts/finding.py cover --add "src/features/media/**"   # the Phase 0.4 inventory
python3 ${CLAUDE_SKILL_DIR}/scripts/finding.py render     # the comments, ready to post (--json feeds post-batch)
python3 ${CLAUDE_SKILL_DIR}/scripts/finding.py stats      # the Phase 4 coverage block
```

`render` refuses while the coverage inventory is empty: without it the Phase 4 block cannot
say what was never examined. For a PR where an inventory adds nothing, say why —
`render --no-inventory "PR из двух файлов, прочитан целиком"` — and the reason goes into
the Phase 4 block instead of the list.

Under pressure — a long PR, a shrinking context window — a rule written in prose gets
quietly relaxed. A tool that exits non-zero does not. If Python is unavailable in the
environment, the rules above still hold; you are then the one enforcing them.

### The claim forms, and how each one dies

The right-hand column is what you run *hoping it fails*. A claim that survives the attempt
is worth posting; one that does not is worth more than the comment would have been.

| Claim | The free check that could kill it | It dies when |
|---|---|---|
| `ломается при <вход / состояние> → <что увидит пользователь>` | read the branch, then `git grep` every call site; best case a failing test | a guard exists higher up the stack, or that input cannot occur |
| `требование "<цитата из тикета>" не реализовано` | search the code that would have to satisfy it | it is implemented somewhere other than where you looked |
| `коллизия <идентификатор> с <ветка>:<файл>` | `git grep -l "<identifier>" origin/<sibling-branch>` | the two live in different scopes and never coexist |
| `расходится с <файл:строка>` | open the sibling, compare along the neighbour-diff axes | the sibling does the same thing — or the sibling is the outdated one |
| `возвращаемое <имя> никто не читает` | `git grep -n "useThing(" -A12` over every call site | a consumer exists |
| `инвариант <какой> ломается при <действии>` | look for the test that would fail | a test already pins it |
| `нарушает правило репо <файл:строки>` (form `rule`, `--rule`) | the script reads and quotes the cited lines | the rule does not cover this file, or the repo config switches it off |
| `поведение, которого не требует тикет: <что>` (form `unrequested`) | search the ticket, related tickets and decisions for it | a requirement or an accepted decision names it |

Two rules keep the grammar honest:

- **Each part is graded separately, and one wrong part sinks the whole finding.** "Breaks
  on an empty list and also leaks the token" is two claims; if the second is wrong, the
  comment as posted was wrong.
- **Some findings are not executable at all** — convention drift, future cost, design fit.
  Their falsification *is* the named sibling, and that is a hard requirement: "inconsistent
  with the module" is arguable, "`X` and `Y` take `dataCy` as a prop, this one hardcodes
  it" is not.

### Verdict

- **подтверждено** — the check was run, the output is attached.
- **предположение** — the mechanism is real but could not be checked; say in one sentence
  *why* (no test environment, the data only exists in production, the sibling branch is not
  fetched).

Anything that is neither does not get posted.

### A refuted hypothesis is not waste

The check that kills your own finding is the most valuable thing that happens in a review,
and it is free. It does two jobs: it stops the same hypothesis being re-derived after the
context window compacts, and it is the only evidence that a subsystem was examined rather
than skimmed. **Write it down** — see the notes file — and report the count in Phase 4.

## The Evidence Ladder

Climb a rung only when the current one can neither confirm nor kill the claim. The rung you
reached caps how severe the finding may be posted as: a 🔴 that blocks the merge cannot rest
on having read the diff.

| Rung | What you do | Max severity it supports |
|---|---|---|
| 0 | read the diff | 🟢 |
| 1 | `git grep` across the repo and the sibling branches; read the neighbours | 🟡 |
| 2 | type-check the **whole project** and filter to the changed files (`tsc <files>` ignores tsconfig; mypy follows imports), lint / build the changed files — commands in the plan | 🟡 |
| 3 | run the existing tests covering the path | 🔴 |
| 4 | write a failing test or a small reproduction | 🔴 |
| 5 | run the application | 🔴 |

Most findings should settle on rungs 1–2. Rungs 4–5 are for the one or two places in a PR
where being wrong is expensive — not for every suspicion.

## The Review Notes File

A long review does not fit in a context window. It compacts, and afterwards the review
quietly continues with a third of the PR in mind. That is the mechanism behind scattered
coverage: a cluster of comments in the first files opened, whole subsystems never examined.

So keep **one page** at `REVIEW-NOTES.md` (in a scratch directory, not committed to the
repo), rewritten as you go. [`scripts/finding.py`](scripts/finding.py) regenerates it after
every `add` / `refute` / `cover` / `plan`, so it can never drift from the findings; by hand,
copy [the template](assets/review-notes-template.md):

```markdown
## Проверено          — с доказательством: файл:строка, вывод команды
## Предполагается     — открытые вопросы, что осталось проверить
## Опровергнуто       — что думал → чем убито
## Покрытие           — инвентарь из Phase 0.4, с отметками
## План               — что дальше
```

Rewrite it as each finding resolves either way, not at the end. Keep it to roughly one
screen: everything on the page has to earn its place, which forces raw sightings to be
compressed into rules. It is the only thing a compaction cannot take away, and re-reading
it is how the review recovers after one.

**Опровергнуто** is the section easiest to skip and most expensive to lose. It is what
stops a second lap around a hypothesis already killed, and it is the raw material for the
coverage statement in Phase 4.

If the same wrong assumption keeps costing this project findings across reviews, promote it
to a persistent `.review/refuted.md` in the repo — a single review has no other way to
accumulate anything.

## Language and Wording (Plain Words, No Jargon)

The review is written for the pull-request author to read and act on — not to
show expertise. Write it in **the reader's own language** (if the conversation
is in Russian, write the findings in Russian) and in **plain, everyday words**.

- **Do not use untranslated anglicisms or transliterated English jargon.** In
  Russian, never write words like "плейсибл", "кламп", "рефетч", "гонка"
  (as a transliteration), "стейл", "нит", "фикс" when a normal word exists.
  In any language, avoid insider shorthand: "plausible", "nit", "altitude",
  "clamp", "refetch", "stale", "guard", "off-by-one", "TOCTOU", "N+1".
- **If a technical term is truly unavoidable, explain it in plain words in
  parentheses the first time it appears.** Examples of the plain form to use:
  - "plausible bug" → "возможная проблема — механизм реальный, но воспроизвести на конкретных данных пока не доказано"
  - "clamp the page number" → "ограничить номер страницы допустимым диапазоном (не больше числа страниц)"
  - "stale state" → "устаревшее значение, оставшееся в состоянии компонента"
  - "race condition" → "состояние гонки — два действия выполняются одновременно и мешают друг другу"
  - "off-by-one" → "ошибка на единицу в границах (например, цикл заходит на один шаг дальше нужного)"
- **Prefer detailed, understandable explanations over terse expert shorthand.**
  For every finding spell out, in plain words: (1) что именно происходит,
  (2) при каких точно условиях это срабатывает, (3) что из-за этого увидит
  пользователь или почему это важно. Одно чуть более длинное, но понятное
  предложение лучше короткого загадочного.
- **Keep severity, but name it in words**, not only symbols or English labels:
  "нужно исправить до мержа" / "стоит поправить" / "необязательно, на усмотрение".
- **Do not water down real problems** to sound polite — plain language means
  clear, not vague. Say directly what breaks and why.

## Posting Review Comments

Read [reference/posting.md](reference/posting.md) before posting — it holds the exact rules and the
commands. The part that must never slip:

- **Inline, one comment per finding**, anchored to the changed line — never a page-level note.
- **First line, exactly:** `**[ai-review-bot]** · Приоритет: <важно | желательно | не важно> · Блокирующее: <да | нет> · <подтверждено | предположение>`.
  A question to the author: `**[ai-review-bot]** · Вопрос · Блокирующее: нет` (`post --question`). A reply
  in a thread also starts with `**[ai-review-bot]**`. The script refuses anything else.
- **Only through the scripts:** `finding.py render --json` → `gitlab_comment.py post-batch`. The
  posting script refuses any body that did not pass the gate; `glab api -f position[...]` silently
  creates page-level notes.
- **Verify** with `gitlab_comment.py threads` that every finding landed as a `DiffNote`.
- **Re-review** works from the open `[ai-review-bot]` threads; a thread closes on re-run evidence, not
  on the author's "done".

## Review Process

### Phase 0: Context Around the Diff (5 minutes) — MANDATORY

**Most missed findings are not inside the diff.** They are in the ticket the diff was
supposed to implement, in the sibling files the new code should have matched, and in the
parallel branch that will land next week. A review that only reads the diff finds only
the bugs a linter almost found. Do all four steps before opening a single changed file.

**0.1 — Read the specification, not just the description.**

Open the ticket linked in the PR **and the related tickets of the same feature**: the
epic, the ticket named in the branch prefix, tickets the description or the code comments
point at. Requirements routinely live in a neighbouring ticket rather than the linked one.

From them, write down a literal list of requirements this PR is meant to satisfy — quote
the sentences, one `finding.py req --add "<quote>" --source "<KEY>"` each. You will check the code against that list in Phase 4, so keep the wording.
Requirements phrased as invariants ("opening a new overlay closes the previous one",
"all of these are built on a single base component", "an unavailable service must not be
read as zero") are the ones implementations quietly skip.

Use whatever ticket tooling the environment provides — a Jira/Confluence skill, the
`glab` / `gh` CLI for the PR itself and its description, or WebFetch. If the tickets are
unreachable, say so in the review instead of silently reviewing without them.

**0.2 — Find out what this PR merges into.**

```bash
git log --oneline origin/<target>..HEAD          # commits under review
git diff --stat origin/<target>...HEAD | tail -1 # true size
```

If the target is **not** the main branch, this is an integration branch, and other
branches are aiming at the same place. That changes what "correct" means: each branch can
be right on its own and still break after the merge.

**0.3 — Cross-check the sibling branches (only when 0.2 says integration branch).**

Textual merge conflicts are Git's job. What you are looking for is the opposite —
**collisions with no conflict**, because the two branches touch different files that
share a global namespace:

```bash
# branches aiming at the same integration branch
git for-each-ref --format='%(refname:short)' refs/remotes/origin | grep -v HEAD

# for each shared global identifier introduced by this PR, look for it elsewhere
git grep -l "<identifier>" origin/<sibling-branch>
```

Global namespaces worth checking, in rough order of how often they bite:

| Namespace | Introduced by | Collision looks like |
|-----------|---------------|----------------------|
| CSS / SCSS class names | any new `.scss` or global `.css` | last stylesheet loaded wins; one component renders wrong |
| Translation keys | new keys in the locale catalogue | one screen's copy overwrites another's |
| Test selectors (`data-cy`, `data-testid`) | new components | specs grab the wrong element |
| Route paths, storage keys, event names, feature flags | new screens/features | silent shadowing |
| Same component name in two directories | copy-paste between features | the wrong one gets imported |

A collision found here is normally the heaviest finding in the review, and it belongs to
*both* PRs — say explicitly which one you expect to change, and that the two authors need
to agree before either merges.

**0.4 — For a large PR, take inventory before reading.**

```bash
git diff --stat origin/<target>...HEAD
git diff --name-only origin/<target>...HEAD | grep -E '\.(tsx?|scss|css|ya?ml|py)$|migrations/'
```

Over ~40 files, unstructured reading produces scattered coverage: a handful of comments
clustered in the first files opened, and whole subsystems never examined. Instead, list
every new component / hook / stylesheet / endpoint / migration first, then walk the list
and mark each one reviewed **in the `Покрытие` section of the notes file** — in your head is
not a place, it does not survive the first compaction. In Phase 4, report what you did
**not** get to — a review that silently covered a third of a PR reads as approval of the
rest.

> Pipe the diff through [`scripts/pr-analyzer.py`](scripts/pr-analyzer.py)
> (`git diff origin/<target>...HEAD | python3 ${CLAUDE_SKILL_DIR}/scripts/pr-analyzer.py`) to triage
> complexity and get a suggested review order.

### Phase 1: Orientation (2-3 minutes)

1. Check PR size against the inventory from 0.4 (>400 lines? Ask to split — but still
   review what is there)
2. Review CI/CD status (tests passing?)
3. Note any relevant architectural decisions
4. Identify the 2-3 files where the actual logic lives, versus the mechanical churn

### Phase 2: High-Level Review (5-10 minutes)

1. **Architecture & Design** - Does the solution fit the problem?
   - For significant changes, consult [Architecture Review Guide](reference/architecture-review-guide.md)
   - Check: SOLID principles, coupling/cohesion, anti-patterns
2. **Performance Assessment** - Are there performance concerns?
   - For performance-critical code, consult [Performance Review Guide](reference/performance-review-guide.md)
   - Check: Algorithm complexity, N+1 queries, memory usage
3. **File Organization** - Are new files in the right places?
4. **Testing Strategy** - Are there tests covering edge cases?

### Phase 3: Line-by-Line Review (10-20 minutes)

Not "open the file and check five boxes" — that produces impressions. Run this loop, once
per suspicion:

1. **Look** — read the changed lines and what they depend on.
2. **Claim** — state the suspicion in one of the forms from *The Gate*, specific enough
   that the repository could contradict it.
3. **Try to kill it** — run the free check from that form's right-hand column. Climb the
   evidence ladder only when the current rung answers neither way.
4. **Record** — a survivor goes to `Проверено` with its evidence, a casualty goes to
   `Опровергнуто` with what killed it. Both go to the notes file; neither goes straight
   into a comment.

Only what survived step 3 is written up in Phase 4.

What to look *for* while running the loop:

- **Logic & Correctness** - Edge cases, boundary errors, null checks, concurrent access
- **Security** - Input validation, injection risks, XSS, sensitive data
- **Performance** - N+1 queries, unnecessary loops, memory leaks
- **Maintainability** - Clear names, single responsibility, comments
- **Reuse** - Before accepting new code, search for existing utilities/helpers that could replace it. Check adjacent files and shared modules for similar patterns. See [Universal Quality Guide](reference/code-quality-universal.md) for anti-patterns like parameter sprawl, leaky abstractions, nested conditionals, stringly-typed code, check-then-act races (TOCTOU), and no-op updates.

For UI diffs, also walk [Frontend Web Specifics](reference/frontend-web-specifics.md) —
global style collisions, list keys, test selectors, translation keys, iframes, overlay
stacking, and the loading/empty/error triad.

#### The neighbour diff (mandatory for every new component, hook, or module)

Reuse asks "does this already exist?". This asks the different question: **"the code next
door does the same job — does this do it the same way?"** Convention drift is invisible
line by line and obvious side by side, which is why it survives diff-only reviews.

For each new unit, name its 2-3 closest siblings — the other dialogs, the other list
screens, the other hooks over the same resource — and compare along these axes:

| Axis | Question |
|------|----------|
| Props / signature | Same shape? Required where the siblings require, optional where they allow? |
| Types | Same source — domain entities where the siblings use domain entities, not raw transport DTOs leaking into UI? |
| States | Same loading / empty / error handling, with retry where the siblings have retry? |
| Test selectors | Passed in as a prop where the siblings take a prop? |
| Styles | Same file layout, same class-name prefix, same tokens? |
| Base component | Built on the shared wrapper the siblings use, or straight onto the UI kit? |
| Naming / i18n scope | Same conventions? |

Two rules make these findings land:

- **Name the sibling.** "Inconsistent with the rest of the module" is arguable; "`X` takes
  `dataCy` as a required prop, `Y` and `Z` too, this one hardcodes it" is not.
- **Grade by future cost, not present damage.** Most drift breaks nothing today. Ask what
  the second call site costs — if the ticket already names one, that moves it from
  optional to worth fixing now.

Two drift patterns deserve a finding on their own:

- **The same PR doing it both ways.** One list renders an error state, the neighbouring
  list on the identical hook does not. That is not a style preference, that is one of the
  two being wrong.
- **An output nobody consumes.** Every value a new hook/service/module returns should have
  a reader. Trace each one:

  ```bash
  git grep -n "return {" -A15 -- path/to/useThing.ts   # what it exposes
  git grep -n "useThing(" -A12                          # what each call site destructures
  ```

  A flag that is computed, stored, returned — and read nowhere — means the behaviour it was
  built for is missing from the UI. That is a functional gap wearing the costume of dead code.

#### Fragile invariants

Beyond "is there a bug here", ask: **what is holding this correct, and would anyone notice
if that support were removed?** Some code is safe only because of a condition that is
nowhere written down and nowhere tested — `sandbox` without `allow-scripts`, an ordering
between two calls, a cache key that must include a field, a guard that must run first.

Report it when all three hold: the invariant is load-bearing, it is not stated at the code
that depends on it, and no test fails if it is broken. The ask is small — a sentence at the
line plus an assertion in a test — so grade it as a should-fix rather than a blocker, and
say plainly what happens the day someone removes it.

### Phase 4: Summary & Decision (3-5 minutes)

1. **Check the code against the requirement list from Phase 0.1.** Give every requirement a
   status with `finding.py req --mark R<n> --status met|partial|missing|unverified` (the evidence
   rules are in [business-logic-review.md](reference/business-logic-review.md)); `finding.py stats`
   prints the table and the compliance level the script computed. This is where unimplemented
   requirements surface, and they never surface any other way:

   | Requirement (quoted from the ticket) | Status | Where |
   |---|---|---|
   | "opening a new overlay closes the previous one" | ❌ not implemented | three independent states in `List.tsx` |
   | "built on a single base overlay component" | ⚠️ partially | two of four go straight to the UI kit |
   | "list shows loading / empty / error with retry" | ✅ | `ChangeLogDialog.tsx` |

   A requirement that is missing is normally a blocker for acceptance even when nothing is
   broken technically — the ticket will be closed as done otherwise.
2. Summarize key concerns
3. **State the coverage honestly, with numbers.** `finding.py stats` prints
   this block; by hand, copy the counts out of the notes file — the refuted ones included:

   > Проверено находок: 7. Отброшено собственными проверками: 4. Осталось предположениями: 2.
   > Осмотрено: `src/features/media/**`, `src/shared/ui/**`. Не осмотрено: миграции, e2e-спеки.

   The refuted count is not an admission of sloppiness — it is the evidence that those
   subsystems were examined rather than skimmed. Silence about a subsystem reads as
   approval of it (see Phase 0.4).
4. Highlight what you liked
5. Make clear decision:
   - ✅ Approve
   - 💬 Comment (minor suggestions)
   - 🔄 Request Changes (must address)
6. Offer to pair if complex

## Severity

Use labels to indicate priority:

- 🔴 `[blocking]` - Must fix before merge
- 🟡 `[important]` - Should fix, discuss if disagree
- 🟢 `[nit]` - Nice to have, not blocking
- 💡 `[suggestion]` - Alternative approach to consider
- 📚 `[learning]` - Educational comment, no action needed
- 🎉 `[praise]` - Good work, keep it up!

**Severity levels:** 🔴 / 🟡 / 🟢 are the three severity tiers used as the standard across all guides in this skill — 🔴 blocks the merge, 🟡 should be addressed, 🟢 is optional. The remaining markers (💡 / 📚 / 🎉) are non-blocking annotations.

**Two axes — take the lower.** The table below grades by the *kind* of finding; the
[Evidence Ladder](#the-evidence-ladder) caps it by the *strength of the evidence*. A
collision that is 🔴 by kind but rests on a diff you only read is posted as 🟡, with the
reason said out loud: "не смог получить соседнюю ветку, чтобы подтвердить".

**Grading the cross-file finding types** (the ones Phase 0 and the neighbour diff produce —
they break nothing *today*, which makes them easy to under-grade):

| Finding type | Default | Escalate to 🔴 when |
|---|---|---|
| Collision with a sibling branch (CSS class, i18n key, selector, route) | 🔴 | it is already 🔴 — nothing merges until the two authors agree |
| Requirement from the ticket not implemented | 🟡 | the requirement is a safety or data-integrity rule |
| Same PR handling the same case two different ways | 🟡 | the worse of the two silently misleads the user (an error rendered as "nothing found") |
| Convention drift from the siblings | 🟢 | the second call site is already named in a ticket |
| Load-bearing invariant, undocumented and untested | 🟡 | breaking it is exploitable rather than merely wrong |

Say which it is in words, and say what the day-it-bites scenario looks like. "Inconsistent"
on its own gets ignored; "when Media Library reuses this dialog, its specs will select the
wrong element" gets fixed.

## Language-Specific Guides

Consult the relevant guide for the language/framework under review:

| Language/Framework | Reference File | Key Topics |
|-------------------|----------------|------------|
| **React** | [React Guide](reference/react.md) | Hooks, useEffect, useMemo/useCallback, component design, Error Boundaries |
| **React (modern stack)** | [React Modern Stack Guide](reference/react-modern-stack.md) | RSC, React 19 Actions, Suspense streaming, TanStack Query v5 — **only if the project uses them** |
| **Frontend / browser** | [Frontend Web Specifics](reference/frontend-web-specifics.md) | Global CSS collisions, list keys, test selectors, i18n keys, iframe `sandbox`, overlay stacking, loading/empty/error |
| **TypeScript** | [TypeScript Guide](reference/typescript.md) | Type safety, async/await, immutability, testing, module resolution, TS 5.x |
| **React SPA checks (2026)** | [React Checks](reference/react-checks.md) | React Compiler, Rules of React lint, React 19 migration, TanStack keys, a11y, forms, ru plurals, knip, dependency-cruiser, ladder commands |
| **Python** | [Python Guide](reference/python.md) | Repo checks discovery, ladder commands (ruff, mypy/pyright, pytest, import-linter), 16 claim forms, style and layering |
| **FastAPI + Pydantic v2** | [FastAPI Guide](reference/python-fastapi.md) | Blocking the event loop, response_model leaks, dependencies with yield and scope, Pydantic v2 changes, version boundaries |
| **NestJS / Node.js** | [NestJS Guide](reference/nestjs.md) | Dependency injection, layered architecture, DTO validation, Guards/Interceptors, circular deps |

## Cross-Cutting Guides

Language-agnostic patterns applicable to all code reviews:

| Topic | Reference File | Key Topics |
|-------|----------------|------------|
| **Architecture Review** | [Architecture Review Guide](reference/architecture-review-guide.md) | SOLID, anti-patterns, coupling/cohesion, dependency direction |
| **Performance Review** | [Performance Review Guide](reference/performance-review-guide.md) | Web Vitals, N+1, algorithm complexity, memory leaks, caching |
| **Security Review** | [Security Review Guide](reference/security-review-guide.md) | SQLi, XSS, CSRF, SSRF, IDOR, command injection, cross-language examples |
| **Universal Quality** | [Universal Quality Guide](reference/code-quality-universal.md) | Reuse audit, parameter sprawl, leaky abstractions, nested conditionals, stringly-typed code, TOCTOU, no-op updates, redundant state |
| **Common Bugs** | [Common Bugs Checklist](reference/common-bugs-checklist.md) | Language-specific bug patterns, common pitfalls |
| **SQL Injection Prevention** | [SQL Injection Guide](reference/cross-cutting/sql-injection-prevention.md) | Parameterized queries, ORM safety, 6 languages, dynamic identifiers, detection |
| **XSS Prevention** | [XSS Prevention Guide](reference/cross-cutting/xss-prevention.md) | Output encoding, CSP, 5 frameworks, input validation vs encoding, detection |
| **N+1 Queries** | [N+1 Queries Guide](reference/cross-cutting/n-plus-one-queries.md) | Eager loading, batch fetching, DataLoader, 5 languages, detection |
| **Error Handling** | [Error Handling Guide](reference/cross-cutting/error-handling-principles.md) | Fail fast, error hierarchy, 7 languages, anti-patterns, logging |
| **Async & Concurrency** | [Concurrency Guide](reference/cross-cutting/async-concurrency-patterns.md) | Goroutines, async/await, actors, structured concurrency, 7 languages |
| **Business logic (mode `business`)** | [Business Logic Review](reference/business-logic-review.md) | Ticket quality gate, quoted requirements, statuses with evidence, business bug classes, `unrequested` |
| **Design (mode `design`)** | [Design Review](reference/design-review.md) | Where rules come from, the `rule` form, dependency direction, what code design is worth a comment |
| **Posting to the MR** | [Posting](reference/posting.md) | Comment format, inline placement via the script, verification, the re-review loop |
| **Review Best Practices** | [Code Review Best Practices](reference/code-review-best-practices.md) | Communication, reviewer mindset, giving feedback, severity labels |

## Additional Resources

- [PR Review Template](assets/pr-review-template.md) - the write-up in Phase 4
- [Review Checklist](assets/review-checklist.md) - quick reference checklist
- [Review Notes Template](assets/review-notes-template.md) - the one page that survives a compaction
- [`scripts/finding.py`](scripts/finding.py) - the gate: refuses a finding with no failure scenario, no evidence and no verdict; renders the comments and the Phase 4 counts
- [`scripts/gitlab_comment.py`](scripts/gitlab_comment.py) - posts the findings as **inline** GitLab discussions (JSON body, self-verifying); also lists threads, replies and resolves
- [`scripts/pr-analyzer.py`](scripts/pr-analyzer.py) - PR complexity triage and a suggested review order
- [`scripts/review_plan.py`](scripts/review_plan.py) - the mode × stack registry: detects the stack from the diff and prints what to read and which repo commands to run
