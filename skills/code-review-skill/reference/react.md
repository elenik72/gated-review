# React Code Review Guide

React review focus: Rules of Hooks, moderation in performance optimization, component design, error boundaries.

> RSC / React 19 Actions / Suspense streaming / TanStack Query have been split out into
> [React Modern Stack Guide](react-modern-stack.md) — read it only if the project actually uses these technologies.
> Platform-agnostic frontend details (global style conflicts, list keys, test selectors, i18n, iframe sandbox) are covered in
> [Frontend Web Specifics](frontend-web-specifics.md).

## Contents

- [Basic Rules of Hooks](#basic-rules-of-hooks)
- [useEffect Patterns](#useeffect-patterns)
- [useMemo / useCallback](#usememo--usecallback)
- [Component Design](#component-design)
- [Error Boundaries & Suspense](#error-boundaries--suspense)
- [Review Checklists](#review-checklists)

---

## Basic Rules of Hooks

```tsx
// ❌ Calling Hooks conditionally — violates the Rules of Hooks
function BadComponent({ isLoggedIn }) {
  if (isLoggedIn) {
    const [user, setUser] = useState(null);  // Error!
  }
  return <div>...</div>;
}

// ✅ Hooks must be called at the top level of the component
function GoodComponent({ isLoggedIn }) {
  const [user, setUser] = useState(null);
  if (!isLoggedIn) return <LoginPrompt />;
  return <div>{user?.name}</div>;
}
```

---

## useEffect Patterns

```tsx
// ❌ Missing or incomplete dependency array
function BadEffect({ userId }) {
  const [user, setUser] = useState(null);
  useEffect(() => {
    fetchUser(userId).then(setUser);
  }, []);  // Missing userId dependency!
}

// ✅ Complete dependency array
function GoodEffect({ userId }) {
  const [user, setUser] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetchUser(userId).then(data => {
      if (!cancelled) setUser(data);
    });
    return () => { cancelled = true; };  // Cleanup function
  }, [userId]);
}

// ❌ useEffect used for derived state (anti-pattern)
function BadDerived({ items }) {
  const [filteredItems, setFilteredItems] = useState([]);
  useEffect(() => {
    setFilteredItems(items.filter(i => i.active));
  }, [items]);  // Unnecessary effect + extra render
  return <List items={filteredItems} />;
}

// ✅ Compute directly during render, or use useMemo
function GoodDerived({ items }) {
  const filteredItems = useMemo(
    () => items.filter(i => i.active),
    [items]
  );
  return <List items={filteredItems} />;
}

// ❌ useEffect used to respond to events
function BadEventEffect() {
  const [query, setQuery] = useState('');
  useEffect(() => {
    if (query) {
      analytics.track('search', { query });  // Should be in an event handler
    }
  }, [query]);
}

// ✅ Run side effects in event handlers
function GoodEvent() {
  const [query, setQuery] = useState('');
  const handleSearch = (q: string) => {
    setQuery(q);
    analytics.track('search', { query: q });
  };
}
```

---

## useMemo / useCallback

```tsx
// ❌ Over-optimization — constants don't need useMemo
function OverOptimized() {
  const config = useMemo(() => ({ timeout: 5000 }), []);  // Pointless
  const handleClick = useCallback(() => {
    console.log('clicked');
  }, []);  // Pointless unless passed to a memo component
}

// ✅ Optimize only when needed
function ProperlyOptimized() {
  const config = { timeout: 5000 };  // Define simple objects directly
  const handleClick = () => console.log('clicked');
}

// ❌ useCallback with always-changing dependencies
function BadCallback({ data }) {
  // data is a new object on every render, so useCallback has no effect
  const process = useCallback(() => {
    return data.map(transform);
  }, [data]);
}

// ✅ useMemo + useCallback used together with React.memo
const MemoizedChild = React.memo(function Child({ onClick, items }) {
  return <div onClick={onClick}>{items.length}</div>;
});

function Parent({ rawItems }) {
  const items = useMemo(() => processItems(rawItems), [rawItems]);
  const handleClick = useCallback(() => {
    console.log(items.length);
  }, [items]);
  return <MemoizedChild onClick={handleClick} items={items} />;
}
```

---

## Component Design

```tsx
// ❌ Defining a component inside a component — creates a new component on every render
function BadParent() {
  function ChildComponent() {  // A new function on every render!
    return <div>child</div>;
  }
  return <ChildComponent />;
}

// ✅ Define the component outside
function ChildComponent() {
  return <div>child</div>;
}
function GoodParent() {
  return <ChildComponent />;
}

// ❌ Props are always new object references
function BadProps() {
  return (
    <MemoizedComponent
      style={{ color: 'red' }}  // New object on every render
      onClick={() => {}}         // New function on every render
    />
  );
}

// ✅ Stable references
const style = { color: 'red' };
function GoodProps() {
  const handleClick = useCallback(() => {}, []);
  return <MemoizedComponent style={style} onClick={handleClick} />;
}
```

---

## Error Boundaries & Suspense

```tsx
// ❌ No error boundary
function BadApp() {
  return (
    <Suspense fallback={<Loading />}>
      <DataComponent />  {/* An error crashes the entire app */}
    </Suspense>
  );
}

// ✅ Error Boundary wraps Suspense
function GoodApp() {
  return (
    <ErrorBoundary fallback={<ErrorUI />}>
      <Suspense fallback={<Loading />}>
        <DataComponent />
      </Suspense>
    </ErrorBoundary>
  );
}
```

---

## Review Checklists

### Rules of Hooks

- [ ] Hooks are called at the top level of components/custom Hooks
- [ ] No Hooks called inside conditions/loops
- [ ] useEffect dependency arrays are complete
- [ ] useEffect has a cleanup function (subscriptions/timers/requests)
- [ ] useEffect is not used to compute derived state

### Performance Optimization (Moderation Principle)

- [ ] Use useMemo/useCallback only where truly needed
- [ ] Use React.memo with stable props references
- [ ] No child components defined inside components
- [ ] No new objects/functions created in JSX (unless passed to non-memo components)
- [ ] Long lists use virtualization (react-window/react-virtual)

### Component Design

- [ ] Each component has a single responsibility and is at most 200 lines
- [ ] Logic is separated from presentation (Custom Hooks)
- [ ] Props interface is clear and typed with TypeScript
- [ ] Avoid Props Drilling (consider Context or composition)

### State Management

- [ ] Keep state close to where it is used (smallest necessary scope)
- [ ] Use useReducer for complex state
- [ ] Use Context or a state library for global state
- [ ] Avoid unnecessary state (derive > store)

### Error Handling

- [ ] Critical areas have an Error Boundary
- [ ] Use Suspense together with an Error Boundary
- [ ] Async operations have error handling

### Testing

- [ ] Use @testing-library/react
- [ ] Query elements with screen
- [ ] Use userEvent instead of fireEvent
- [ ] Prefer *ByRole queries
- [ ] Test behavior, not implementation details
