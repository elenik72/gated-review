# Guides — which reference to open

Open what the plan of `finding.py init` lists for the mode and the stack; this page is the full index.

## Language-Specific Guides

Consult the relevant guide for the language/framework under review:

| Language/Framework | Reference File | Key Topics |
|-------------------|----------------|------------|
| **React** | [React Guide](react.md) | Hooks, useEffect, useMemo/useCallback, component design, Error Boundaries |
| **React (modern stack)** | [React Modern Stack Guide](react-modern-stack.md) | RSC, React 19 Actions, Suspense streaming, TanStack Query v5 — **only if the project uses them** |
| **Frontend / browser** | [Frontend Web Specifics](frontend-web-specifics.md) | Global CSS collisions, list keys, test selectors, i18n keys, iframe `sandbox`, overlay stacking, loading/empty/error |
| **TypeScript** | [TypeScript Guide](typescript.md) | Type safety, async/await, immutability, testing, module resolution, TS 5.x |
| **React SPA checks (2026)** | [React Checks](react-checks.md) | React Compiler, Rules of React lint, React 19 migration, TanStack keys, a11y, forms, ru plurals, knip, dependency-cruiser, ladder commands |
| **Python** | [Python Guide](python.md) | Repo checks discovery, ladder commands (ruff, mypy/pyright, pytest, import-linter), 16 claim forms, style and layering |
| **FastAPI + Pydantic v2** | [FastAPI Guide](python-fastapi.md) | Blocking the event loop, response_model leaks, dependencies with yield and scope, Pydantic v2 changes, version boundaries |
| **NestJS / Node.js** | [NestJS Guide](nestjs.md) | Dependency injection, layered architecture, DTO validation, Guards/Interceptors, circular deps |

## Cross-Cutting Guides

Language-agnostic patterns applicable to all code reviews:

| Topic | Reference File | Key Topics |
|-------|----------------|------------|
| **Architecture Review** | [Architecture Review Guide](architecture-review-guide.md) | SOLID, anti-patterns, coupling/cohesion, dependency direction |
| **Performance Review** | [Performance Review Guide](performance-review-guide.md) | Web Vitals, N+1, algorithm complexity, memory leaks, caching |
| **Security Review** | [Security Review Guide](security-review-guide.md) | SQLi, XSS, CSRF, SSRF, IDOR, command injection, cross-language examples |
| **Universal Quality** | [Universal Quality Guide](code-quality-universal.md) | Reuse audit, parameter sprawl, leaky abstractions, nested conditionals, stringly-typed code, TOCTOU, no-op updates, redundant state |
| **Common Bugs** | [Common Bugs Checklist](common-bugs-checklist.md) | Language-specific bug patterns, common pitfalls |
| **SQL Injection Prevention** | [SQL Injection Guide](cross-cutting/sql-injection-prevention.md) | Parameterized queries, ORM safety, 6 languages, dynamic identifiers, detection |
| **XSS Prevention** | [XSS Prevention Guide](cross-cutting/xss-prevention.md) | Output encoding, CSP, 5 frameworks, input validation vs encoding, detection |
| **N+1 Queries** | [N+1 Queries Guide](cross-cutting/n-plus-one-queries.md) | Eager loading, batch fetching, DataLoader, 5 languages, detection |
| **Error Handling** | [Error Handling Guide](cross-cutting/error-handling-principles.md) | Fail fast, error hierarchy, 7 languages, anti-patterns, logging |
| **Async & Concurrency** | [Concurrency Guide](cross-cutting/async-concurrency-patterns.md) | Goroutines, async/await, actors, structured concurrency, 7 languages |
| **Business logic (mode `business`)** | [Business Logic Review](business-logic-review.md) | Ticket quality gate, quoted requirements, statuses with evidence, business bug classes, `unrequested` |
| **Design (mode `design`)** | [Design Review](design-review.md) | Where rules come from, the `rule` form, dependency direction, what code design is worth a comment |
| **Posting to the MR** | [Posting](posting.md) | Comment format, inline placement via the script, verification, the re-review loop |
| **Review Best Practices** | [Code Review Best Practices](code-review-best-practices.md) | Communication, reviewer mindset, giving feedback, severity labels |

## Additional Resources

- [PR Review Template](../assets/pr-review-template.md) - the write-up in Phase 4
- [Review Checklist](../assets/review-checklist.md) - quick reference checklist
- [Review Notes Template](../assets/review-notes-template.md) - the one page that survives a compaction
- [`scripts/finding.py`](../scripts/finding.py) - the gate: refuses a finding with no failure scenario, no evidence and no verdict; renders the comments and the Phase 4 counts
- [`scripts/gitlab_comment.py`](../scripts/gitlab_comment.py) - posts the findings as **inline** GitLab discussions (JSON body, self-verifying); also lists threads, replies and resolves
- [`scripts/pr-analyzer.py`](../scripts/pr-analyzer.py) - PR complexity triage and a suggested review order
- [`scripts/review_plan.py`](../scripts/review_plan.py) - the mode × stack registry: detects the stack from the diff and prints what to read and which repo commands to run
