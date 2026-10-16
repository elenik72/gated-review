# Frontend Web Specifics

Browser-level details that framework guides skip. These are the findings that hide
*between* files: global CSS, list keys, test selectors, translation keys, iframes,
overlay stacking, and the loading/empty/error triad.

Read this for any PR that touches UI. Most items here are cheap greps — run them,
do not eyeball them.

## Contents

- [Global stylesheets and class-name collisions](#global-stylesheets-and-class-name-collisions)
- [List keys](#list-keys)
- [Test selectors (data-cy / data-testid)](#test-selectors-data-cy--data-testid)
- [Translation keys and scopes](#translation-keys-and-scopes)
- [iframe, sandbox, and raw HTML](#iframe-sandbox-and-raw-html)
- [Overlays, portals, and stacking](#overlays-portals-and-stacking)
- [The loading / empty / error triad](#the-loading--empty--error-triad)

---

## Global stylesheets and class-name collisions

If the project imports plain `.css` / `.scss` (not CSS Modules, not styled-components),
**every class name is a global identifier**. Two components may each own a file that
compiles fine, passes review in isolation, and still fight at runtime — the stylesheet
that loads last wins.

This is the single most-missed class of frontend bug, because nothing in the diff looks
wrong. It only shows up after a merge.

**How to check.** For every new top-level class in the PR, grep the whole tree — and the
sibling branches (see the Phase 0 cross-branch step in [SKILL.md](../SKILL.md)):

```bash
# 1. every top-level class declared by the PR
git diff origin/<target>...HEAD -- '*.scss' '*.css' | grep -E '^\+\.[a-z]' | sort -u

# 2. is any of them already declared elsewhere in this branch?
git grep -n "^\.the-class-name" -- '*.scss' '*.css'

# 3. and in the branches merging into the same integration branch?
for b in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin \
           | grep -v HEAD); do
  git grep -l "^\.the-class-name" "$b" -- '*.scss' '*.css'
done
```

**Red flags**

- A generic BEM root (`.preview-issues`, `.entity-list`, `.dialog-body`) with no
  feature prefix — collision bait.
- The same root class declared in two files with *different* property sets. Even one
  shared property (`background`, `padding`, `display`, `max-height`) means one of the
  two components will render wrong.
- A component moved or copied between directories while keeping its class names —
  the old copy usually still exists on another branch.

**What to write.** Name both files, list the properties that actually conflict, and say
which side will lose. "Rename one of them" is not enough of an ask — propose the
namespace (`.template-builder-editor-preview-issues` vs
`.template-builder-dialog-preview-issues`) or propose merging the components.

## List keys

`key` must be **unique among siblings** and **stable across renders**.

```tsx
// ❌ Index: after a delete or reorder React reuses the wrong DOM and state
{items.map((item, i) => <Row key={i} item={item} />)}

// ❌ Concatenated optional fields: when both are missing, two items get the same key
{issues.map(issue => <li key={`${issue.code}-${issue.slug ?? issue.mediaId}`} />)}
//   two issues with the same code and undefined slug and mediaId → "code-undefined" ×2

// ❌ Random value: changes on every render, the whole subtree remounts, inputs lose focus
{items.map(item => <Row key={crypto.randomUUID()} item={item} />)}

// ✅ A real id
{items.map(item => <Row key={item.id} item={item} />)}

// ✅ No id: optional fields with the index as a fallback
{issues.map((issue, i) => <li key={`${issue.code}-${issue.slug ?? issue.mediaId ?? i}`} />)}
```

**Ask two questions of every `key` built by string concatenation:**

1. Can every field in it be `undefined` or missing? If yes, can two different items
   collapse to the same string?
2. Is the set of values closed? An "open set of codes" comment next to the type — or a
   `string` where you expected a union — means unknown values *will* arrive, and the
   fallback branch is reachable.

Consequence is usually mild (a console warning, occasionally swapped rows or lost input
state), so it is a 🟢 — but it is a one-line fix, so still worth writing up.

## Test selectors (data-cy / data-testid)

E2E selectors are an API. A shared component that hardcodes its own selectors cannot be
used twice on the same page, and cannot be told apart by the specs.

**How to check.** Compare against siblings, not against theory:

```bash
# how do neighbouring components of the same kind take their selectors?
git grep -n "dataCy\|data-testid" -- 'src/**/components/*Dialog.tsx'
```

If every sibling declares `dataCy: string` as a required prop and the new one writes the
literal inline, that is a convention break — even if there is only one call site today.

**Escalate from 🟢 to 🟡 when the component is *planned* to be reused**: a second call
site named in the ticket, a "will also be used by X" line in the description, or a
sibling tab that obviously needs the same dialog. Parameterising now costs one prop;
after the second call site lands, it costs a rename plus every spec that referenced the
old selector.

**Also check**

- Selectors are derived, not re-typed: `` data-cy={`${dataCy}-retry`} `` beats a second
  literal that can drift from the first.
- New interactive elements (retry buttons, "show more", pagination) have selectors at
  all — otherwise the next spec author invents one by CSS class and couples tests to
  styling.

## Translation keys and scopes

```bash
# every new t("…") key in the diff
git diff origin/<target>...HEAD -- '*.tsx' | grep -oE '\bt\("[^"]+"' | sort -u
# does it exist in the catalogue?
git grep -n "the_key:" -- '*/translations/*.yml'
```

- Every new key exists in **all** locale files, not just the default one. A missing key
  usually renders as the raw key string in the UI, which reaches production silently.
- The scope passed to the scoped-translation hook matches where the component lives.
  Two components with the same name in different directories often end up sharing a
  scope by copy-paste and then quietly overwrite each other's strings.
- No user-visible string is hardcoded in JSX while its neighbours go through `t()`.

## iframe, sandbox, and raw HTML

Any place the app renders HTML it did not author — `srcDoc`, `dangerouslySetInnerHTML`,
a preview of user-authored content, an email template rendered by the backend — is a
security boundary. Ask **what is holding the boundary up, and would we notice if it
were removed?**

- `sandbox="allow-same-origin"` with **no** `allow-scripts` is safe: the parent can read
  `contentDocument`, and nothing inside executes. Adding `allow-scripts` alongside
  `allow-same-origin` breaks the sandbox completely — the frame can reach into the
  parent origin. That combination is XSS in the app's own origin, with the session.
- When the safety depends on an attribute *not* being extended, say so **at the
  attribute** and **in a test**. A comment three paragraphs above explaining the
  mechanism is not a guard; the next person adding interactive preview will not read it.

```js
// the test that actually protects the invariant
expect(frame.getAttribute("sandbox")).toBe("allow-same-origin")
```

- Check who authors the HTML *now*. If this PR changed the source (client-side assembly →
  a backend render endpoint that inlines other users' content blocks and media), the
  threat model changed with it, even though the attribute did not.
- `dangerouslySetInnerHTML`: is the value sanitised, and sanitised on the side that
  cannot be bypassed? Trusting "the backend already escapes it" needs a link to where.

## Overlays, portals, and stacking

- **Independent state = simultaneous overlays.** Three `useState`s named `previewing`,
  `showingUsage`, `changeLogFor` in one component mean all three can be open at once.
  If the spec says "opening a new overlay closes the previous one", this is a
  requirement gap, not a nit. The fix is usually one discriminated-union state
  (`{ kind: "preview" | "usage" | "changeLog", entity }`) instead of N booleans.
- Every overlay of the same family should sit on the **same base component**. Check for
  one that goes straight to the UI-kit `Dialog` while its siblings go through the
  project's wrapper — it will drift on padding, close behaviour, scroll locking, and
  escape handling.
- Focus and keyboard: does `Esc` close it, does focus return to the trigger, is focus
  trapped while open? Usually inherited from the wrapper — which is exactly why the
  component that skipped the wrapper is worth flagging.

## The loading / empty / error triad

Every async surface needs all three states, and **an error must not be rendered as
"empty"** — the user reads "there is nothing here" and acts on it.

**How to check.** Follow the state out of the hook, not into it:

```bash
# hook exposes an error flag …
git grep -n "return {" -A15 -- src/**/useSomething.ts
# … who actually reads it?
git grep -n "error" -- src/**/List.tsx src/**/*Dialog.tsx
```

A flag that is computed, stored, and returned but has **zero consumers** is a real
finding: the work was done and then dropped on the floor. Two call sites of one hook
where only one renders the error is stronger still — same PR, same hook, two different
behaviours for the user.

Also check:

- Retry exists and re-runs the failed request (not a full page reload).
- Empty-because-no-data and empty-because-search-found-nothing are different copy.
- A failed *refetch* does not blank out data already on screen.
- The pagination case: does an out-of-range page render "nothing found" instead of
  falling back to the last existing page?

---

## Review Checklist

- [ ] New global CSS/SCSS class names are unique across the tree **and across sibling branches**
- [ ] No two files declare the same top-level class with different properties
- [ ] Every `key` is unique among siblings even when its optional fields are missing
- [ ] No index/random values used as `key` in reorderable lists
- [ ] Shared components take test selectors as a prop, like their siblings
- [ ] New interactive elements have test selectors
- [ ] New translation keys exist in every locale file; scope matches the component
- [ ] `sandbox` / `dangerouslySetInnerHTML` invariants are documented at the code and asserted in a test
- [ ] Overlay family shares one base component; only one overlay can be open at a time
- [ ] Every async surface has loading, empty, and error states — error is never shown as empty
- [ ] Every value a new hook returns has at least one consumer
