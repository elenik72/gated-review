# Review process — phases 0 to 4, and how to grade

The gate, the evidence ladder and the notes file are in [SKILL.md](../SKILL.md); this page is the
order of work. The plan `finding.py init` prints names it, so it is read at the start of every
review and again from disk after a context compaction.

## The phases

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

> Pipe the diff through [`scripts/pr-analyzer.py`](../scripts/pr-analyzer.py)
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
   - For significant changes, consult [Architecture Review Guide](architecture-review-guide.md)
   - Check: SOLID principles, coupling/cohesion, anti-patterns
2. **Performance Assessment** - Are there performance concerns?
   - For performance-critical code, consult [Performance Review Guide](performance-review-guide.md)
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
- **Reuse** - Before accepting new code, search for existing utilities/helpers that could replace it. Check adjacent files and shared modules for similar patterns. See [Universal Quality Guide](code-quality-universal.md) for anti-patterns like parameter sprawl, leaky abstractions, nested conditionals, stringly-typed code, check-then-act races (TOCTOU), and no-op updates.

For UI diffs, also walk [Frontend Web Specifics](frontend-web-specifics.md) —
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
   rules are in [business-logic-review.md](business-logic-review.md)); `finding.py stats`
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
[Evidence Ladder](../SKILL.md#the-evidence-ladder) caps it by the *strength of the evidence*. A
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

