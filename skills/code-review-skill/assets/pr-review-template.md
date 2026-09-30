# PR Review Template

Copy and use this template for your code reviews.

---

## Summary

[Brief overview of what was reviewed - 1-2 sentences]

**PR Size:** [Small/Medium/Large] (~X lines, X files)
**Target branch:** [main / integration branch — if integration, name the sibling branches checked]
**Tickets read:** [linked ticket + related tickets of the same feature]
**Review Time:** [X minutes]

## Coverage

Copy the counts out of `REVIEW-NOTES.md` — the refuted ones included. They are the evidence
that a subsystem was examined rather than skimmed.

> Проверено находок: **[N]**. Отброшено собственными проверками: **[M]**.
> Осталось предположениями: **[K]**.

Examined: [subsystems / directories actually reviewed]
Not examined: [what was left out and why — silence about a subsystem reads as approval]

Checked and found fine (worth naming — it tells the author where not to worry):
- [hypothesis] → [what killed it]

## Requirement Compliance

Each requirement quoted literally from the ticket, checked against the code.

| Requirement (quoted) | Status | Where |
|---|---|---|
| "[quote]" | ✅ implemented | `path/to/File.tsx:NN` |
| "[quote]" | ⚠️ partially | [what is missing] |
| "[quote]" | ❌ not implemented | [what the code does instead] |

## Cross-Branch Collisions

Shared global names introduced by this PR, checked against the branches merging into the
same target (CSS classes, i18n keys, test selectors, routes, storage keys).

- [ ] None found — or:
- 🔴 `[identifier]` also declared in `[branch]:[file]` — [what breaks after both merge, and which PR should change]

## Strengths

- [What was done well]
- [Good patterns or approaches used]
- [Improvements from previous code]

## Consistency With Neighbours

For each new component/hook, the siblings it was compared against and what differs.

| New unit | Compared against | Difference | Severity |
|---|---|---|---|
| `[Component]` | `[SiblingA]`, `[SiblingB]` | [e.g. hardcodes its test selectors while both siblings take a prop] | 🟢 / 🟡 |

- [ ] The same PR does not handle the same case two different ways
- [ ] Every value a new hook returns has a consumer

## Architecture & Performance

**Architecture Assessment**
- [ ] Separation of concerns — are responsibilities clearly divided?
- [ ] Module responsibilities — does each module have a single purpose?
- [ ] Dependency direction — do dependencies flow toward stability?
- [ ] Consistent with existing patterns and conventions

> See [Architecture Review Guide](../reference/architecture-review-guide.md) for detailed SOLID, anti-pattern, and coupling analysis.

**Performance Assessment**
- [ ] Algorithm complexity — any O(n²) or worse on large inputs?
- [ ] Memory impact — large allocations, leaks, unbounded growth?
- [ ] I/O impact — excessive API calls, unbatched writes, missing caching?
- [ ] Database queries — N+1 risks, missing indexes, unoptimized joins?

> See [Performance Review Guide](../reference/performance-review-guide.md) for comprehensive Web Vitals, N+1, and caching guidance.

## Required Changes

Every entry carries its evidence and its verdict. A 🔴 needs rung 3+ (a test run or a
reproduction); without it, post as 🟡 and say why it could not be confirmed.

🔴 **[blocking]** · подтверждено [Issue description]
> **Ломается при:** [input / state] → [what the user sees]
> **Location:** `file.ts:123`
> **Проверка:** `[the command that could have killed this]` → [its output]
> [Suggested fix]

## Important Suggestions

🟡 **[important]** · подтверждено | предположение [Issue description]
> **Why this matters:** [the day-it-bites scenario]
> **Проверка:** [command + output] — or, if not executable: **сосед:** `path/File.tsx:NN`
> **Если предположение:** [why it could not be checked]
> [Suggested approach]

## Minor Suggestions

🟢 **[nit]** [Minor improvement suggestion]

💡 **[suggestion]** [Alternative approach to consider]

## Learning Notes

📚 [Educational context worth sharing about X]

📚 [Background behind design decision Y]

## Security Considerations

- [ ] No hardcoded secrets
- [ ] Input validation present
- [ ] Authorization checks in place
- [ ] No SQL/XSS injection risks
- [ ] CSRF protection for state-changing operations
- [ ] Sensitive data not leaked in logs/errors
- [ ] Dependency vulnerabilities checked (npm audit / pip audit / cargo audit)

> See [Security Review Guide](../reference/security-review-guide.md) for comprehensive injection, XSS, CSRF, secrets, and auth checklist.

## Test Coverage

- [ ] Unit tests added/updated
- [ ] Edge cases covered
- [ ] Error cases tested

## Verdict

**[ ] ✅ Approve** - Ready to merge
**[ ] 💬 Comment** - Minor suggestions, can merge
**[ ] 🔄 Request Changes** - Must address blocking issues

---

## Quick Copy Templates

### Blocking Issue
```
🔴 **[blocking]** · подтверждено [Title]

[Description of the issue]

**Ломается при:** [input / state] → [what the user sees]

**Location:** `file.ts:123`

**Проверка:** `pnpm vitest run media.spec.ts` → 1 failed

**Suggested fix:**
\`\`\`typescript
// Your suggested code
\`\`\`
```

### Important Suggestion
```
🟡 **[important]** [Title]

[Why this is important]

**Consider:**
- Option A: [description]
- Option B: [description]
```

### Minor Suggestion
```
🟢 **[nit]** [Suggestion]

Not blocking, but consider [improvement].
```

### Praise
```
🎉 **[praise]** Great work on [specific thing]!

[Why this is good]
```

### Learning
```
📚 **[learning]** [Educational note]

For context, [X] works this way because [Y]. No action needed — just sharing.
```
