# React Modern Stack Review Guide (RSC / React 19 / TanStack Query)

> **Applies only when the project actually uses these.** Check first:
> `grep -rn '"react"' package.json` (React 19+ for Actions), `grep -rn "'use client'\|'use server'" src` (RSC),
> `grep -rn '@tanstack/react-query' package.json` (TanStack Query).
> If none of them are present, skip this file entirely — see [React Guide](react.md) instead.

## 目录

- [Server Components (RSC)](#server-components-rsc)
- [React 19 Actions & Forms](#react-19-actions--forms)
- [Suspense & Streaming SSR](#suspense--streaming-ssr)
- [TanStack Query v5](#tanstack-query-v5)
- [Review Checklists](#review-checklists)

---

## Server Components (RSC)

```tsx
// ❌ 在 Server Component 中使用客户端特性
// app/page.tsx (Server Component by default)
function BadServerComponent() {
  const [count, setCount] = useState(0);  // Error! No hooks in RSC
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
}

// ✅ 交互逻辑提取到 Client Component
// app/counter.tsx
'use client';
function Counter() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
}

// app/page.tsx (Server Component)
async function GoodServerComponent() {
  const data = await fetchData();  // 可以直接 await
  return (
    <div>
      <h1>{data.title}</h1>
      <Counter />  {/* 客户端组件 */}
    </div>
  );
}

// ❌ 'use client' 放置不当 — 整个树都变成客户端
// layout.tsx
'use client';  // 这会让所有子组件都成为客户端组件
export default function Layout({ children }) { ... }

// ✅ 只在需要交互的组件使用 'use client'
// 将客户端逻辑隔离到叶子组件
```

---

## React 19 Actions & Forms

React 19 引入了 Actions 系统和新的表单处理 Hooks，简化异步操作和乐观更新。

### useActionState

```tsx
// ❌ 传统方式：多个状态变量
function OldForm() {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState(null);

  const handleSubmit = async (formData: FormData) => {
    setIsPending(true);
    setError(null);
    try {
      const result = await submitForm(formData);
      setData(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setIsPending(false);
    }
  };
}

// ✅ React 19: useActionState 统一管理
import { useActionState } from 'react';

function NewForm() {
  const [state, formAction, isPending] = useActionState(
    async (prevState, formData: FormData) => {
      try {
        const result = await submitForm(formData);
        return { success: true, data: result };
      } catch (e) {
        return { success: false, error: e.message };
      }
    },
    { success: false, data: null, error: null }
  );

  return (
    <form action={formAction}>
      <input name="email" />
      <button disabled={isPending}>
        {isPending ? 'Submitting...' : 'Submit'}
      </button>
      {state.error && <p className="error">{state.error}</p>}
    </form>
  );
}
```

### useFormStatus

```tsx
// ❌ Props 透传表单状态
function BadSubmitButton({ isSubmitting }) {
  return <button disabled={isSubmitting}>Submit</button>;
}

// ✅ useFormStatus 访问父 <form> 状态（无需 props）
import { useFormStatus } from 'react-dom';

function SubmitButton() {
  const { pending, data, method, action } = useFormStatus();
  // 注意：必须在 <form> 内部的子组件中使用
  return (
    <button disabled={pending}>
      {pending ? 'Submitting...' : 'Submit'}
    </button>
  );
}

// ❌ useFormStatus 在 form 同级组件中调用——不工作
function BadForm() {
  const { pending } = useFormStatus();  // 这里无法获取状态！
  return (
    <form action={action}>
      <button disabled={pending}>Submit</button>
    </form>
  );
}

// ✅ useFormStatus 必须在 form 的子组件中
function GoodForm() {
  return (
    <form action={action}>
      <SubmitButton />  {/* useFormStatus 在这里面调用 */}
    </form>
  );
}
```

### useOptimistic

```tsx
// ❌ 等待服务器响应再更新 UI
function SlowLike({ postId, likes }) {
  const [likeCount, setLikeCount] = useState(likes);
  const [isPending, setIsPending] = useState(false);

  const handleLike = async () => {
    setIsPending(true);
    const newCount = await likePost(postId);  // 等待...
    setLikeCount(newCount);
    setIsPending(false);
  };
}

// ✅ useOptimistic 即时反馈，失败自动回滚
import { useOptimistic, useTransition } from 'react';

function FastLike({ postId, likes }) {
  const [optimisticLikes, addOptimisticLike] = useOptimistic(
    likes,
    (currentLikes, increment: number) => currentLikes + increment
  );

  const [, startTransition] = useTransition();
  const handleLike = () => {
    // ⚠️ 乐观更新必须在 Action / startTransition 内：在普通 onClick 里直接调用，
    // React 会警告 "optimistic state update occurred outside a Transition or Action" 并立刻回滚
    startTransition(async () => {
      addOptimisticLike(1);      // 立即更新 UI
      await likePost(postId);    // 失败时 Transition 结束，值回到 likes
    });
  };

  return <button onClick={handleLike}>{optimisticLikes} likes</button>;
}
```

### Server Actions (Next.js 15+)

```tsx
// ❌ 客户端调用 API
'use client';
function ClientForm() {
  const handleSubmit = async (formData: FormData) => {
    const res = await fetch('/api/submit', {
      method: 'POST',
      body: formData,
    });
    // ...
  };
}

// ✅ Server Action + useActionState
// actions.ts
'use server';
type State = { ok: boolean; error?: string } | null;

export async function createPost(prevState: State, formData: FormData): Promise<State> {
  // ⚠️ Server Action 是公开的 POST 端点：页面上的检查对它无效，每个 action 自己做 authn/authz + 校验
  const session = await auth();
  if (!session) return { ok: false, error: 'unauthorized' };
  const parsed = PostSchema.safeParse({ title: formData.get('title') });
  if (!parsed.success) return { ok: false, error: 'invalid' };
  await db.posts.create({ ...parsed.data, authorId: session.userId });
  revalidatePath('/posts');
  return { ok: true };
}

// form.tsx
'use client';
import { createPost } from './actions';

function PostForm() {
  const [state, formAction, isPending] = useActionState(createPost, null);
  return (
    <form action={formAction}>
      <input name="title" />
      <SubmitButton />
    </form>
  );
}
```

---

## Suspense & Streaming SSR

Suspense 和 Streaming 是 React 18+ 的核心特性，在 2025 年的 Next.js 15 等框架中广泛使用。

### 基础 Suspense

```tsx
// ❌ 传统加载状态管理
function OldComponent() {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchData().then(setData).finally(() => setIsLoading(false));
  }, []);

  if (isLoading) return <Spinner />;
  return <DataView data={data} />;
}

// ✅ Suspense 声明式加载状态
function NewComponent() {
  return (
    <Suspense fallback={<Spinner />}>
      <DataView />  {/* 内部使用 use() 或支持 Suspense 的数据获取 */}
    </Suspense>
  );
}
```

### 多个独立 Suspense 边界

```tsx
// ❌ 单一边界——所有内容一起加载
function BadLayout() {
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <Header />
      <MainContent />  {/* 慢 */}
      <Sidebar />      {/* 快 */}
    </Suspense>
  );
}

// ✅ 独立边界——各部分独立流式传输
function GoodLayout() {
  return (
    <>
      <Header />  {/* 立即显示 */}
      <div className="flex">
        <Suspense fallback={<ContentSkeleton />}>
          <MainContent />  {/* 独立加载 */}
        </Suspense>
        <Suspense fallback={<SidebarSkeleton />}>
          <Sidebar />      {/* 独立加载 */}
        </Suspense>
      </div>
    </>
  );
}
```

### Next.js 15 Streaming

```tsx
// app/page.tsx - 自动 Streaming
export default async function Page() {
  // ⚠️ 这个 await 会阻塞本段，直到最近的 <Suspense> / loading.tsx 为止；
  // Next 16 开启 cacheComponents 时，<Suspense> 之外的未缓存访问会让构建失败
  const data = await fetchSlowData();
  return <div>{data}</div>;
}

// app/loading.tsx - 自动 Suspense 边界
export default function Loading() {
  return <Skeleton />;
}
```

### use() Hook (React 19)

```tsx
// ✅ 在组件中读取 Promise
import { use } from 'react';

function Comments({ commentsPromise }) {
  const comments = use(commentsPromise);  // 自动触发 Suspense
  return (
    <ul>
      {comments.map(c => <li key={c.id}>{c.text}</li>)}
    </ul>
  );
}

// 父组件创建 Promise，子组件消费
function Post({ postId }) {
  // ⚠️ 只有 Post 是 Server Component 时才成立。客户端组件里每次渲染都会新建 Promise（未缓存），
  // 应从 loader / 缓存库（TanStack Query 的 queryClient.ensureQueryData 等）取得同一个 Promise
  const commentsPromise = fetchComments(postId);  // 不 await
  return (
    <article>
      <PostContent id={postId} />
      <Suspense fallback={<CommentsSkeleton />}>
        <Comments commentsPromise={commentsPromise} />
      </Suspense>
    </article>
  );
}
```

---

## TanStack Query v5

TanStack Query 是 React 生态中最流行的数据获取库，v5 是当前稳定版本。

### 基础配置

```tsx
// ❌ 不正确的默认配置
const queryClient = new QueryClient();  // 默认配置可能不适合

// ✅ 生产环境推荐配置
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,  // 5 分钟内数据视为新鲜
      gcTime: 1000 * 60 * 30,    // 30 分钟后垃圾回收（v5 重命名）
      retry: 3,
      refetchOnWindowFocus: false,  // 根据需求决定
    },
  },
});
```

### queryOptions (v5 新增)

```tsx
// ❌ 重复定义 queryKey 和 queryFn
function Component1() {
  const { data } = useQuery({
    queryKey: ['users', userId],
    queryFn: () => fetchUser(userId),
  });
}

function prefetchUser(queryClient, userId) {
  queryClient.prefetchQuery({
    queryKey: ['users', userId],  // 重复！
    queryFn: () => fetchUser(userId),  // 重复！
  });
}

// ✅ queryOptions 统一定义，类型安全
import { queryOptions } from '@tanstack/react-query';

const userQueryOptions = (userId: string) =>
  queryOptions({
    queryKey: ['users', userId],
    queryFn: () => fetchUser(userId),
  });

function Component1({ userId }) {
  const { data } = useQuery(userQueryOptions(userId));
}

function prefetchUser(queryClient, userId) {
  queryClient.prefetchQuery(userQueryOptions(userId));
}

// getQueryData 也是类型安全的
const user = queryClient.getQueryData(userQueryOptions(userId).queryKey);
```

### 常见陷阱

```tsx
// ❌ staleTime 为 0 导致过度请求
useQuery({
  queryKey: ['data'],
  queryFn: fetchData,
  // staleTime 默认为 0，每次组件挂载都会 refetch
});

// ✅ 设置合理的 staleTime
useQuery({
  queryKey: ['data'],
  queryFn: fetchData,
  staleTime: 1000 * 60,  // 1 分钟内不会重新请求
});

// ❌ 在 queryFn 中使用不稳定的引用
function BadQuery({ filters }) {
  useQuery({
    queryKey: ['items'],  // queryKey 没有包含 filters！
    queryFn: () => fetchItems(filters),  // filters 变化不会触发重新请求
  });
}

// ✅ queryKey 包含所有影响数据的参数
function GoodQuery({ filters }) {
  useQuery({
    queryKey: ['items', filters],  // filters 是 queryKey 的一部分
    queryFn: () => fetchItems(filters),
  });
}
```

### useSuspenseQuery

> **重要限制**：useSuspenseQuery 与 useQuery 有显著差异，选择前需了解其限制。

#### useSuspenseQuery 的限制

| 特性 | useQuery | useSuspenseQuery |
|------|----------|------------------|
| `enabled` 选项 | ✅ 支持 | ❌ 不支持 |
| `placeholderData` | ✅ 支持 | ❌ 不支持 |
| `data` 类型 | `T \| undefined` | `T`（保证有值）|
| 错误处理 | `error` 属性 | 抛出到 Error Boundary |
| 加载状态 | `isLoading` 属性 | 挂起到 Suspense |

#### 不支持 enabled 的替代方案

```tsx
// ❌ 使用 useQuery + enabled 实现条件查询
function BadSuspenseQuery({ userId }) {
  const { data } = useSuspenseQuery({
    queryKey: ['user', userId],
    queryFn: () => fetchUser(userId),
    enabled: !!userId,  // useSuspenseQuery 不支持 enabled！
  });
}

// ✅ 组件组合实现条件渲染
function GoodSuspenseQuery({ userId }) {
  // useSuspenseQuery 保证 data 是 T 不是 T | undefined
  const { data } = useSuspenseQuery({
    queryKey: ['user', userId],
    queryFn: () => fetchUser(userId),
  });
  return <UserProfile user={data} />;
}

function Parent({ userId }) {
  if (!userId) return <NoUserSelected />;
  return (
    <Suspense fallback={<UserSkeleton />}>
      <GoodSuspenseQuery userId={userId} />
    </Suspense>
  );
}
```

#### 错误处理差异

```tsx
// ❌ useSuspenseQuery 没有 error 属性
function BadErrorHandling() {
  const { data, error } = useSuspenseQuery({...});
  if (error) return <Error />;  // error 总是 null！
}

// ✅ 使用 Error Boundary 处理错误
function GoodErrorHandling() {
  return (
    <ErrorBoundary fallback={<ErrorMessage />}>
      <Suspense fallback={<Loading />}>
        <DataComponent />
      </Suspense>
    </ErrorBoundary>
  );
}

function DataComponent() {
  // 错误会抛出到 Error Boundary
  const { data } = useSuspenseQuery({
    queryKey: ['data'],
    queryFn: fetchData,
  });
  return <Display data={data} />;
}
```

#### 何时选择 useSuspenseQuery

```tsx
// ✅ 适合场景：
// 1. 数据总是需要的（无条件查询）
// 2. 组件必须有数据才能渲染
// 3. 使用 React 19 的 Suspense 模式
// 4. 服务端组件 + 客户端 hydration

// ❌ 不适合场景：
// 1. 条件查询（根据用户操作触发）
// 2. 需要 placeholderData 或初始数据
// 3. 需要在组件内处理 loading/error 状态
// 4. 多个查询有依赖关系

// ✅ 多个独立查询用 useSuspenseQueries
function MultipleQueries({ userId }) {
  const [userQuery, postsQuery] = useSuspenseQueries({
    queries: [
      { queryKey: ['user', userId], queryFn: () => fetchUser(userId) },
      { queryKey: ['posts', userId], queryFn: () => fetchPosts(userId) },
    ],
  });
  // 两个查询并行执行，都完成后组件渲染
  return <Profile user={userQuery.data} posts={postsQuery.data} />;
}
```

### 乐观更新 (v5 简化)

```tsx
// ❌ 手动管理缓存的乐观更新（复杂）
const mutation = useMutation({
  mutationFn: updateTodo,
  onMutate: async (newTodo) => {
    await queryClient.cancelQueries({ queryKey: ['todos'] });
    const previousTodos = queryClient.getQueryData(['todos']);
    queryClient.setQueryData(['todos'], (old) => [...old, newTodo]);
    return { previousTodos };
  },
  onError: (err, newTodo, context) => {
    queryClient.setQueryData(['todos'], context.previousTodos);
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['todos'] });
  },
});

// ✅ v5 简化：使用 variables 进行乐观 UI
function TodoList() {
  const { data: todos } = useQuery(todosQueryOptions);
  const { mutate, variables, isPending } = useMutation({
    mutationFn: addTodo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['todos'] });
    },
  });

  return (
    <ul>
      {todos?.map(todo => <TodoItem key={todo.id} todo={todo} />)}
      {/* 乐观显示正在添加的 todo */}
      {isPending && <TodoItem todo={variables} isOptimistic />}
    </ul>
  );
}
```

### v5 状态字段变化

```tsx
// v4: isLoading 表示首次加载或后续获取
// v5: isPending 表示没有数据，isLoading = isPending && isFetching

const { data, isPending, isFetching, isLoading } = useQuery({...});

// isPending: 缓存中没有数据（首次加载）
// isFetching: 正在请求中（包括后台刷新）
// isLoading: isPending && isFetching（首次加载中）

// ❌ v4 代码直接迁移
if (isLoading) return <Spinner />;  // v5 中行为可能不同

// ✅ 明确意图
if (isPending) return <Spinner />;  // 没有数据时显示加载
// 或
if (isLoading) return <Spinner />;  // 首次加载中
```

---

## Review Checklists

### Server Components (RSC)

- [ ] 'use client' 只用于需要交互的组件
- [ ] Server Component 不使用 Hooks/事件处理
- [ ] 客户端组件尽量放在叶子节点
- [ ] 数据获取在 Server Component 中进行

### React 19 Forms

- [ ] 使用 useActionState 替代多个 useState
- [ ] useFormStatus 在 form 子组件中调用
- [ ] useOptimistic 不用于关键业务（支付等）
- [ ] Server Action 正确标记 'use server'

### Suspense & Streaming

- [ ] 按用户体验需求划分 Suspense 边界
- [ ] 每个 Suspense 有对应的 Error Boundary
- [ ] 提供有意义的 fallback（骨架屏 > Spinner）
- [ ] 避免在 layout 层级 await 慢数据

### TanStack Query

- [ ] queryKey 包含所有影响数据的参数
- [ ] 设置合理的 staleTime（不是默认 0）
- [ ] useSuspenseQuery 不使用 enabled
- [ ] Mutation 成功后 invalidate 相关查询
- [ ] 理解 isPending vs isLoading 区别
