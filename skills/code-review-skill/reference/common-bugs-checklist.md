# Common Bugs Checklist

Quick-reference bug patterns organized by category. For detailed code examples, explanations, and comprehensive review checklists, see the dedicated language guides linked below.

## Universal Issues

### Logic Errors
- [ ] Off-by-one errors in loops and array access
- [ ] Incorrect boolean logic (De Morgan's law violations)
- [ ] Missing null/undefined checks
- [ ] Race conditions in concurrent code
- [ ] Incorrect comparison operators (`==` vs `===`, `=` vs `==`)
- [ ] Integer overflow/underflow
- [ ] Floating point comparison issues

### Resource Management
- [ ] Memory leaks (unclosed connections, listeners)
- [ ] File handles not closed
- [ ] Database connections not released
- [ ] Event listeners not removed
- [ ] Timers/intervals not cleared

### Error Handling
- [ ] Swallowed exceptions (empty catch blocks)
- [ ] Generic exception handling hiding specific errors
- [ ] Missing error propagation
- [ ] Incorrect error types thrown
- [ ] Missing finally/cleanup blocks

## TypeScript/JavaScript

- [ ] `==` instead of `===`
- [ ] Using `any` — prefer proper types or `unknown` with type guards
- [ ] Missing `await` on async calls
- [ ] Unhandled promise rejections (no try-catch around await)
- [ ] `this` context lost in callbacks
- [ ] Missing `key` prop in lists
- [ ] Closure capturing stale loop variable
- [ ] `parseInt` without radix parameter
- [ ] Modifying array/object during iteration

**Full guide:** [TypeScript Review Guide](typescript.md)

## React / React 19

- [ ] Hooks called conditionally or in loops (violates Rules of Hooks)
- [ ] `useEffect` dependency array incomplete or incorrect
- [ ] `useEffect` missing cleanup function (subscriptions, timers, fetches)
- [ ] `useEffect` used for derived state (use `useMemo` instead)
- [ ] `useMemo`/`useCallback` over-used or used without `React.memo`
- [ ] Component defined inside another component (re-mounts every render)
- [ ] Unstable props (inline objects/functions passed to memo components)
- [ ] Direct mutation of props
- [ ] List missing `key` or using array index as key (reorderable lists)
- [ ] Server Component using client APIs (`useState`, `useEffect`, `onClick`)
- [ ] `'use client'` on parent making entire subtree client-side
- [ ] `useActionState` calling `setState` instead of returning new state
- [ ] `useFormStatus` called in same component as `<form>` (must be in child)
- [ ] `useOptimistic` used for critical operations (payments, deletions)
- [ ] Single Suspense boundary for entire page (slow blocks fast)
- [ ] Missing Error Boundary wrapping Suspense
- [ ] `use()` Hook receiving a new Promise each render

**TanStack Query v5:**
- [ ] `queryKey` missing parameters that affect data
- [ ] Default `staleTime: 0` causing excessive refetches
- [ ] `useSuspenseQuery` with `enabled` option (not supported)
- [ ] Mutation not invalidating related queries on success
- [ ] Optimistic update missing rollback in `onError`
- [ ] Using v4 array syntax (`useQuery(['key'], fn)`) instead of v5 object syntax

**Testing:**
- [ ] Using `container.querySelector` instead of `screen.getByRole`
- [ ] Using `fireEvent` instead of `userEvent`
- [ ] Testing implementation details instead of user-visible behavior
- [ ] Using `getBy*` for async content (use `findBy*`)

**Full guide:** [React Review Guide](react.md)

## SQL

- [ ] String concatenation for queries (SQL injection risk) — use parameterized queries
- [ ] Missing indexes on filtered/joined columns
- [ ] `SELECT *` instead of specific columns
- [ ] N+1 query patterns
- [ ] Missing `LIMIT` on large tables
- [ ] Not handling `NULL` comparisons correctly (`IS NULL` vs `= NULL`)
- [ ] Missing transactions for related operations
- [ ] Incorrect JOIN types
- [ ] Collation / case sensitivity surprises across databases (MySQL vs Postgres defaults)
- [ ] Date and timezone handling errors (naive timestamps, server-local `NOW()`, DST)

**See also:** [Security Review Guide](security-review-guide.md) for SQL injection prevention

## API Design

- [ ] Inconsistent resource naming
- [ ] Wrong HTTP methods (POST for idempotent operations)
- [ ] Missing pagination for list endpoints
- [ ] Incorrect status codes
- [ ] Missing rate limiting
- [ ] Missing input validation and sanitization
- [ ] Trusting client-side validation only

## Testing

- [ ] Testing implementation details instead of behavior
- [ ] Missing edge case tests
- [ ] Flaky tests (non-deterministic)
- [ ] Tests with external dependencies (no mocks)
- [ ] Missing negative tests (error cases)
- [ ] Overly complex test setup
