# React Code Review Guide

React 审查重点：Hooks 规则、性能优化的适度性、组件设计、错误边界。

> RSC / React 19 Actions / Suspense streaming / TanStack Query 已拆分到
> [React Modern Stack Guide](react-modern-stack.md) — 只在项目真的用到这些技术时才读它。
> 平台无关的前端细节（全局样式冲突、列表 key、测试选择器、i18n、iframe sandbox）见
> [Frontend Web Specifics](frontend-web-specifics.md)。

## 目录

- [基础 Hooks 规则](#基础-hooks-规则)
- [useEffect 模式](#useeffect-模式)
- [useMemo / useCallback](#usememo--usecallback)
- [组件设计](#组件设计)
- [Error Boundaries & Suspense](#error-boundaries--suspense)
- [Review Checklists](#review-checklists)

---

## 基础 Hooks 规则

```tsx
// ❌ 条件调用 Hooks — 违反 Hooks 规则
function BadComponent({ isLoggedIn }) {
  if (isLoggedIn) {
    const [user, setUser] = useState(null);  // Error!
  }
  return <div>...</div>;
}

// ✅ Hooks 必须在组件顶层调用
function GoodComponent({ isLoggedIn }) {
  const [user, setUser] = useState(null);
  if (!isLoggedIn) return <LoginPrompt />;
  return <div>{user?.name}</div>;
}
```

---

## useEffect 模式

```tsx
// ❌ 依赖数组缺失或不完整
function BadEffect({ userId }) {
  const [user, setUser] = useState(null);
  useEffect(() => {
    fetchUser(userId).then(setUser);
  }, []);  // 缺少 userId 依赖！
}

// ✅ 完整的依赖数组
function GoodEffect({ userId }) {
  const [user, setUser] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetchUser(userId).then(data => {
      if (!cancelled) setUser(data);
    });
    return () => { cancelled = true; };  // 清理函数
  }, [userId]);
}

// ❌ useEffect 用于派生状态（反模式）
function BadDerived({ items }) {
  const [filteredItems, setFilteredItems] = useState([]);
  useEffect(() => {
    setFilteredItems(items.filter(i => i.active));
  }, [items]);  // 不必要的 effect + 额外渲染
  return <List items={filteredItems} />;
}

// ✅ 直接在渲染时计算，或用 useMemo
function GoodDerived({ items }) {
  const filteredItems = useMemo(
    () => items.filter(i => i.active),
    [items]
  );
  return <List items={filteredItems} />;
}

// ❌ useEffect 用于事件响应
function BadEventEffect() {
  const [query, setQuery] = useState('');
  useEffect(() => {
    if (query) {
      analytics.track('search', { query });  // 应该在事件处理器中
    }
  }, [query]);
}

// ✅ 在事件处理器中执行副作用
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
// ❌ 过度优化 — 常量不需要 useMemo
function OverOptimized() {
  const config = useMemo(() => ({ timeout: 5000 }), []);  // 无意义
  const handleClick = useCallback(() => {
    console.log('clicked');
  }, []);  // 如果不传给 memo 组件，无意义
}

// ✅ 只在需要时优化
function ProperlyOptimized() {
  const config = { timeout: 5000 };  // 简单对象直接定义
  const handleClick = () => console.log('clicked');
}

// ❌ useCallback 依赖总是变化
function BadCallback({ data }) {
  // data 每次渲染都是新对象，useCallback 无效
  const process = useCallback(() => {
    return data.map(transform);
  }, [data]);
}

// ✅ useMemo + useCallback 配合 React.memo 使用
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

## 组件设计

```tsx
// ❌ 在组件内定义组件 — 每次渲染都创建新组件
function BadParent() {
  function ChildComponent() {  // 每次渲染都是新函数！
    return <div>child</div>;
  }
  return <ChildComponent />;
}

// ✅ 组件定义在外部
function ChildComponent() {
  return <div>child</div>;
}
function GoodParent() {
  return <ChildComponent />;
}

// ❌ Props 总是新对象引用
function BadProps() {
  return (
    <MemoizedComponent
      style={{ color: 'red' }}  // 每次渲染新对象
      onClick={() => {}}         // 每次渲染新函数
    />
  );
}

// ✅ 稳定的引用
const style = { color: 'red' };
function GoodProps() {
  const handleClick = useCallback(() => {}, []);
  return <MemoizedComponent style={style} onClick={handleClick} />;
}
```

---

## Error Boundaries & Suspense

```tsx
// ❌ 没有错误边界
function BadApp() {
  return (
    <Suspense fallback={<Loading />}>
      <DataComponent />  {/* 错误会导致整个应用崩溃 */}
    </Suspense>
  );
}

// ✅ Error Boundary 包裹 Suspense
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

### Hooks 规则

- [ ] Hooks 在组件/自定义 Hook 顶层调用
- [ ] 没有条件/循环中调用 Hooks
- [ ] useEffect 依赖数组完整
- [ ] useEffect 有清理函数（订阅/定时器/请求）
- [ ] 没有用 useEffect 计算派生状态

### 性能优化（适度原则）

- [ ] useMemo/useCallback 只用于真正需要的场景
- [ ] React.memo 配合稳定的 props 引用
- [ ] 没有在组件内定义子组件
- [ ] 没有在 JSX 中创建新对象/函数（除非传给非 memo 组件）
- [ ] 长列表使用虚拟化（react-window/react-virtual）

### 组件设计

- [ ] 组件职责单一，不超过 200 行
- [ ] 逻辑与展示分离（Custom Hooks）
- [ ] Props 接口清晰，使用 TypeScript
- [ ] 避免 Props Drilling（考虑 Context 或组合）

### 状态管理

- [ ] 状态就近原则（最小必要范围）
- [ ] 复杂状态用 useReducer
- [ ] 全局状态用 Context 或状态库
- [ ] 避免不必要的状态（派生 > 存储）

### 错误处理

- [ ] 关键区域有 Error Boundary
- [ ] Suspense 配合 Error Boundary 使用
- [ ] 异步操作有错误处理

### 测试

- [ ] 使用 @testing-library/react
- [ ] 用 screen 查询元素
- [ ] 用 userEvent 代替 fireEvent
- [ ] 优先使用 *ByRole 查询
- [ ] 测试行为而非实现细节
