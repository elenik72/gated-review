# Code Review Quick Checklist

Quick reference checklist for code reviews.

## Context Around the Diff (5 min) — do this first

- [ ] Read the linked ticket **and the related tickets of the same feature**
- [ ] Write down the requirements as literal quotes (checked against the code at the end)
- [ ] Identify the target branch — is it main, or an integration/feature branch?
- [ ] If integration branch: list the sibling branches aiming at the same target
- [ ] Cross-check shared global names against those branches: CSS classes, i18n keys,
      test selectors, routes, storage keys, component names
- [ ] For a large PR: inventory every new component / hook / stylesheet / endpoint before reading
- [ ] Open `REVIEW-NOTES.md` from [the template](review-notes-template.md) and put that
      inventory in `Покрытие` — it is the only thing that survives a context compaction

## Pre-Review (2 min)

- [ ] Check PR size (<400 lines ideal)
- [ ] Verify CI/CD status (tests passing?)
- [ ] Spot the 2-3 files with the real logic versus the mechanical churn

## Architecture & Design (5 min)

- [ ] Solution fits the problem
- [ ] Consistent with existing patterns
- [ ] No simpler approach exists
- [ ] Will it scale?
- [ ] Changes in right location

## Logic & Correctness (10 min)

- [ ] Edge cases handled
- [ ] Null/undefined checks present
- [ ] Off-by-one errors checked
- [ ] Race conditions considered
- [ ] Error handling complete
- [ ] Correct data types used

## Security (5 min)

- [ ] No hardcoded secrets
- [ ] Input validated/sanitized
- [ ] SQL injection prevented
- [ ] XSS prevented
- [ ] Authorization checks present
- [ ] Sensitive data protected

## Performance (3 min)

- [ ] No N+1 queries
- [ ] Expensive operations optimized
- [ ] Large lists paginated
- [ ] No memory leaks
- [ ] Caching considered where appropriate

## Testing (5 min)

- [ ] Tests exist for new code
- [ ] Edge cases tested
- [ ] Error cases tested
- [ ] Tests are readable
- [ ] Tests are deterministic

## Consistency With Neighbours (5 min)

For every new component / hook / module, compare against its 2-3 closest siblings:

- [ ] Props/signature shaped the same way (required vs optional matches)
- [ ] Types come from the same layer (domain entities, not raw transport DTOs in the UI)
- [ ] Loading / empty / error states handled the same way, retry where siblings retry
- [ ] Test selectors passed as a prop where siblings take a prop
- [ ] Built on the shared base component siblings use, not straight onto the UI kit
- [ ] Styles, naming, i18n scope follow the same conventions
- [ ] **The same PR does not handle the same case two different ways**
- [ ] **Every value a new hook returns has at least one consumer**

## Frontend / Browser (5 min, UI PRs)

> Full detail: [Frontend Web Specifics](../reference/frontend-web-specifics.md)

- [ ] New global CSS/SCSS class names unique across the tree and sibling branches
- [ ] List `key` unique even when its optional fields are missing; no index/random keys
- [ ] New translation keys exist in every locale file
- [ ] `sandbox` / `dangerouslySetInnerHTML` invariants documented at the code and asserted in a test
- [ ] Only one overlay can be open at a time (if the spec says so)
- [ ] Error state is never rendered as "nothing found"

## Fragile Invariants (2 min)

- [ ] What keeps this code correct is written down where it is depended on
- [ ] A test fails if that support is removed

## Requirement Compliance (3 min)

- [ ] Every quoted requirement from the ticket marked ✅ / ⚠️ / ❌ with a location
- [ ] Coverage stated honestly: which parts of a large PR were not examined

## Code Quality (3 min)

- [ ] Clear variable/function names
- [ ] No code duplication
- [ ] Functions do one thing
- [ ] Complex code commented
- [ ] No magic numbers

## Documentation (2 min)

- [ ] Public APIs documented
- [ ] README updated if needed
- [ ] Breaking changes noted
- [ ] Complex logic explained

---

## Before Posting Anything — the gate (per finding)

> Full rules: *The Gate* in [SKILL.md](../SKILL.md). The paid action is the comment; `grep`,
> the type-checker and one test run are free.
>
> `python3 <skill>/scripts/finding.py add …` enforces every box below and exits non-zero when one is
> missing. Refusing costs nothing; posting an unverified claim does.

- [ ] Stated as a falsifiable claim, not an impression
- [ ] The free check that could have killed it was run — and it survived
- [ ] The output of that check is in the comment, **or** a concrete sibling is named
      (`path/File.tsx:NN`), never "the rest of the module"
- [ ] Verdict attached: **подтверждено** (check run) or **предположение** (with the reason
      it could not be checked)
- [ ] Severity is the lower of the two axes: kind of finding, and rung of evidence reached
- [ ] Anything failing these is asked as a question or dropped — not posted as a fact
- [ ] Whatever the check *did* kill is written to `Опровергнуто`, not silently forgotten

---

## Severity Labels

| Label | Meaning | Action |
|-------|---------|--------|
| 🔴 `[blocking]` | Must fix | Block merge |
| 🟡 `[important]` | Should fix | Discuss if disagree |
| 🟢 `[nit]` | Nice to have | Non-blocking |
| 💡 `[suggestion]` | Alternative | Consider |
| 📚 `[learning]` | Educational comment | No action needed |
| 🎉 `[praise]` | Good work | Celebrate! |

**Two axes, take the lower.** The table grades by kind of finding. The evidence ladder in
[SKILL.md](../SKILL.md) caps it by how the claim was checked: rung 0 (read the diff) tops
out at 🟢, rungs 1–2 (`grep` / type-check) at 🟡, and only a test run or a reproduction
(rungs 3–5) supports a 🔴 that blocks the merge.

---

## Decision Matrix

| Situation | Decision |
|-----------|----------|
| Critical security issue | 🔴 Block, fix immediately |
| Breaking change without migration | 🔴 Block |
| Missing error handling | 🟡 Should fix |
| No tests for new code | 🟡 Should fix |
| Style preference | 🟢 Non-blocking |
| Minor naming improvement | 🟢 Non-blocking |
| Clever but working code | 💡 Suggest simpler |

---

## Time Budget

This checklist is designed for a **lightweight quick review**. For comprehensive reviews covering architecture and performance analysis, use the full four-phase process in [SKILL.md](../SKILL.md) (19–36 minutes). Smaller PRs trend toward the lower end of each phase; larger PRs toward the upper end.

| PR Size | Quick Review | Full Review (4-phase) |
|---------|-------------|----------------------|
| < 100 lines | 10–15 min | ~19–28 min |
| 100–400 lines | 20–40 min | ~28–36 min |
| > 400 lines | Ask to split — and still review what is there, by inventory (Phase 0.4) | Ask to split — same |

---

## Red Flags

Watch for these patterns:

- `// TODO` in production code
- `console.log` left in code
- Commented out code
- `any` type in TypeScript
- Empty catch blocks
- `unwrap()` in Rust production code
- Magic numbers/strings
- Copy-pasted code blocks
- Missing null checks
- Hardcoded URLs/credentials
- Hardcoded test selectors in a shared component
- A generic top-level CSS class with no feature prefix
- A hook returning a flag that no call site reads
- `sandbox` on an iframe with no comment saying what must not be added to it
