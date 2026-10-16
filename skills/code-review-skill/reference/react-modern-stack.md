# React Modern Stack Review Guide (RSC / React 19 / TanStack Query)

> **Applies only when the project actually uses these.** Check first:
> `grep -rn '"react"' package.json` (React 19+ for Actions), `grep -rn "'use client'\|'use server'" src` (RSC),
> `grep -rn '@tanstack/react-query' package.json` (TanStack Query).
> If none of them are present, skip this file entirely — see [React Guide](react.md) instead.

## Contents

- [Server Components (RSC)](#server-components-rsc)
- [React 19 Actions & Forms](#react-19-actions--forms)
- [Suspense & Streaming SSR](#suspense--streaming-ssr)
- [TanStack Query v5](#tanstack-query-v5)
- [Review Checklists](#review-checklists)

---

## Server Components (RSC)

```tsx
// ❌ Using client-side features in a Server Component
// app/page.tsx (Server Component by default)
function BadServerComponent() {
  const [count, setCount] = useState(0);  // Error! No hooks in RSC
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
}

// ✅ Interactive logic extracted into a Client Component
// app/counter.tsx
'use client';
function Counter() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
}

// app/page.tsx (Server Component)
async function GoodServerComponent() {
  const data = await fetchData();  // Can await directly
  return (
    <div>
      <h1>{data.title}</h1>
      <Counter />  {/* Client component */}
    </div>
  );
}

// ❌ 'use client' misplaced - the whole tree becomes client-side
// layout.tsx
'use client';  // This makes every child component a client component
export default function Layout({ children }) { ... }

// ✅ Use 'use client' only on components that need interactivity
// Isolate client logic in leaf components
```

---

## React 19 Actions & Forms

React 19 introduces the Actions system and new form-handling Hooks, simplifying async operations and optimistic updates.

### useActionState

```tsx
// ❌ Traditional approach: multiple state variables
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

// ✅ React 19: useActionState manages state in one place
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
// ❌ Props pass-through of form state
function BadSubmitButton({ isSubmitting }) {
  return <button disabled={isSubmitting}>Submit</button>;
}

// ✅ useFormStatus reads the parent <form> status (no props needed)
import { useFormStatus } from 'react-dom';

function SubmitButton() {
  const { pending, data, method, action } = useFormStatus();
  // Note: must be used in a child component inside the <form>
  return (
    <button disabled={pending}>
      {pending ? 'Submitting...' : 'Submit'}
    </button>
  );
}

// ❌ useFormStatus called in the same component as the form - does not work
function BadForm() {
  const { pending } = useFormStatus();  // Status is not available here!
  return (
    <form action={action}>
      <button disabled={pending}>Submit</button>
    </form>
  );
}

// ✅ useFormStatus must be called in a child component of the form
function GoodForm() {
  return (
    <form action={action}>
      <SubmitButton />  {/* useFormStatus is called inside this component */}
    </form>
  );
}
```

### useOptimistic

```tsx
// ❌ Waiting for the server response before updating the UI
function SlowLike({ postId, likes }) {
  const [likeCount, setLikeCount] = useState(likes);
  const [isPending, setIsPending] = useState(false);

  const handleLike = async () => {
    setIsPending(true);
    const newCount = await likePost(postId);  // Waiting...
    setLikeCount(newCount);
    setIsPending(false);
  };
}

// ✅ useOptimistic gives instant feedback and rolls back automatically on failure
import { useOptimistic, useTransition } from 'react';

function FastLike({ postId, likes }) {
  const [optimisticLikes, addOptimisticLike] = useOptimistic(
    likes,
    (currentLikes, increment: number) => currentLikes + increment
  );

  const [, startTransition] = useTransition();
  const handleLike = () => {
    // ⚠️ Optimistic updates must run inside an Action / startTransition: if called directly in a plain onClick,
    // React warns "optimistic state update occurred outside a Transition or Action" and rolls back immediately
    startTransition(async () => {
      addOptimisticLike(1);      // Update the UI immediately
      await likePost(postId);    // On failure the Transition ends and the value goes back to likes
    });
  };

  return <button onClick={handleLike}>{optimisticLikes} likes</button>;
}
```

### Server Actions (Next.js 15+)

```tsx
// ❌ Calling the API from the client
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
  // ⚠️ A Server Action is a public POST endpoint: checks on the page do not protect it, so each action must do its own authn/authz + validation
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

Suspense and Streaming are core features of React 18+ and are widely used in frameworks such as Next.js 15 in 2025.

### Basic Suspense

```tsx
// ❌ Traditional loading-state management
function OldComponent() {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchData().then(setData).finally(() => setIsLoading(false));
  }, []);

  if (isLoading) return <Spinner />;
  return <DataView data={data} />;
}

// ✅ Suspense: declarative loading state
function NewComponent() {
  return (
    <Suspense fallback={<Spinner />}>
      <DataView />  {/* Uses use() or Suspense-enabled data fetching internally */}
    </Suspense>
  );
}
```

### Multiple Independent Suspense Boundaries

```tsx
// ❌ Single boundary - everything loads together
function BadLayout() {
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <Header />
      <MainContent />  {/* Slow */}
      <Sidebar />      {/* Fast */}
    </Suspense>
  );
}

// ✅ Independent boundaries - each part streams on its own
function GoodLayout() {
  return (
    <>
      <Header />  {/* Shown immediately */}
      <div className="flex">
        <Suspense fallback={<ContentSkeleton />}>
          <MainContent />  {/* Loads independently */}
        </Suspense>
        <Suspense fallback={<SidebarSkeleton />}>
          <Sidebar />      {/* Loads independently */}
        </Suspense>
      </div>
    </>
  );
}
```

### Next.js 15 Streaming

```tsx
// app/page.tsx - automatic Streaming
export default async function Page() {
  // ⚠️ This await blocks this segment up to the nearest <Suspense> / loading.tsx;
  // with cacheComponents enabled in Next 16, uncached access outside <Suspense> fails the build
  const data = await fetchSlowData();
  return <div>{data}</div>;
}

// app/loading.tsx - automatic Suspense boundary
export default function Loading() {
  return <Skeleton />;
}
```

### use() Hook (React 19)

```tsx
// ✅ Reading a Promise in a component
import { use } from 'react';

function Comments({ commentsPromise }) {
  const comments = use(commentsPromise);  // Automatically triggers Suspense
  return (
    <ul>
      {comments.map(c => <li key={c.id}>{c.text}</li>)}
    </ul>
  );
}

// The parent creates the Promise, the child consumes it
function Post({ postId }) {
  // ⚠️ Only valid if Post is a Server Component. In a client component every render creates a new (uncached) Promise,
  // so get the same Promise from a loader / cache library (TanStack Query's queryClient.ensureQueryData, etc.)
  const commentsPromise = fetchComments(postId);  // No await
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

TanStack Query is the most popular data-fetching library in the React ecosystem; v5 is the current stable version.

### Basic Configuration

```tsx
// ❌ Unsuitable default configuration
const queryClient = new QueryClient();  // Defaults may not fit

// ✅ Recommended production configuration
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,  // Data is considered fresh for 5 minutes
      gcTime: 1000 * 60 * 30,    // Garbage-collected after 30 minutes (renamed in v5)
      retry: 3,
      refetchOnWindowFocus: false,  // Decide based on requirements
    },
  },
});
```

### queryOptions (New in v5)

```tsx
// ❌ queryKey and queryFn defined twice
function Component1() {
  const { data } = useQuery({
    queryKey: ['users', userId],
    queryFn: () => fetchUser(userId),
  });
}

function prefetchUser(queryClient, userId) {
  queryClient.prefetchQuery({
    queryKey: ['users', userId],  // Duplicate!
    queryFn: () => fetchUser(userId),  // Duplicate!
  });
}

// ✅ queryOptions defines them once, type-safe
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

// getQueryData is also type-safe
const user = queryClient.getQueryData(userQueryOptions(userId).queryKey);
```

### Common Pitfalls

```tsx
// ❌ staleTime of 0 causes excessive requests
useQuery({
  queryKey: ['data'],
  queryFn: fetchData,
  // staleTime defaults to 0, so every component mount triggers a refetch
});

// ✅ Set a reasonable staleTime
useQuery({
  queryKey: ['data'],
  queryFn: fetchData,
  staleTime: 1000 * 60,  // No refetch within 1 minute
});

// ❌ Using an unstable reference in queryFn
function BadQuery({ filters }) {
  useQuery({
    queryKey: ['items'],  // queryKey does not include filters!
    queryFn: () => fetchItems(filters),  // Changes to filters do not trigger a refetch
  });
}

// ✅ queryKey includes every parameter that affects the data
function GoodQuery({ filters }) {
  useQuery({
    queryKey: ['items', filters],  // filters is part of the queryKey
    queryFn: () => fetchItems(filters),
  });
}
```

### useSuspenseQuery

> **Important limitations**: useSuspenseQuery differs significantly from useQuery; know its limitations before choosing it.

#### useSuspenseQuery Limitations

| Feature | useQuery | useSuspenseQuery |
|------|----------|------------------|
| `enabled` option | ✅ Supported | ❌ Not supported |
| `placeholderData` | ✅ Supported | ❌ Not supported |
| `data` type | `T \| undefined` | `T` (guaranteed to have a value) |
| Error handling | `error` property | Thrown to the Error Boundary |
| Loading state | `isLoading` property | Suspends to Suspense |

#### Alternative to the Unsupported enabled Option

```tsx
// ❌ Using useQuery + enabled for a conditional query
function BadSuspenseQuery({ userId }) {
  const { data } = useSuspenseQuery({
    queryKey: ['user', userId],
    queryFn: () => fetchUser(userId),
    enabled: !!userId,  // useSuspenseQuery does not support enabled!
  });
}

// ✅ Conditional rendering via component composition
function GoodSuspenseQuery({ userId }) {
  // useSuspenseQuery guarantees data is T, not T | undefined
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

#### Error Handling Differences

```tsx
// ❌ useSuspenseQuery has no error property
function BadErrorHandling() {
  const { data, error } = useSuspenseQuery({...});
  if (error) return <Error />;  // error is always null!
}

// ✅ Handle errors with an Error Boundary
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
  // Errors are thrown to the Error Boundary
  const { data } = useSuspenseQuery({
    queryKey: ['data'],
    queryFn: fetchData,
  });
  return <Display data={data} />;
}
```

#### When to Choose useSuspenseQuery

```tsx
// ✅ Suitable scenarios:
// 1. The data is always needed (unconditional query)
// 2. The component cannot render without the data
// 3. Using React 19's Suspense pattern
// 4. Server components + client hydration

// ❌ Unsuitable scenarios:
// 1. Conditional queries (triggered by user actions)
// 2. Needs placeholderData or initial data
// 3. Needs to handle loading/error states inside the component
// 4. Multiple queries depend on each other

// ✅ Use useSuspenseQueries for multiple independent queries
function MultipleQueries({ userId }) {
  const [userQuery, postsQuery] = useSuspenseQueries({
    queries: [
      { queryKey: ['user', userId], queryFn: () => fetchUser(userId) },
      { queryKey: ['posts', userId], queryFn: () => fetchPosts(userId) },
    ],
  });
  // Both queries run in parallel; the component renders once both complete
  return <Profile user={userQuery.data} posts={postsQuery.data} />;
}
```

### Optimistic Updates (Simplified in v5)

```tsx
// ❌ Optimistic update with manual cache management (complex)
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

// ✅ Simplified in v5: use variables for the optimistic UI
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
      {/* Optimistically show the todo being added */}
      {isPending && <TodoItem todo={variables} isOptimistic />}
    </ul>
  );
}
```

### v5 Status Field Changes

```tsx
// v4: isLoading means the initial load or a subsequent fetch
// v5: isPending means no data, isLoading = isPending && isFetching

const { data, isPending, isFetching, isLoading } = useQuery({...});

// isPending: No data in the cache (initial load)
// isFetching: A request is in flight (including background refetch)
// isLoading: isPending && isFetching (initial load in progress)

// ❌ Migrating v4 code as-is
if (isLoading) return <Spinner />;  // Behavior may differ in v5

// ✅ Make the intent explicit
if (isPending) return <Spinner />;  // Show loading when there is no data
// or
if (isLoading) return <Spinner />;  // Initial load in progress
```

---

## Review Checklists

### Server Components (RSC)

- [ ] 'use client' is used only on components that need interactivity
- [ ] Server Component does not use Hooks/event handlers
- [ ] Client components are placed at leaf nodes where possible
- [ ] Data fetching happens in a Server Component

### React 19 Forms

- [ ] Use useActionState instead of multiple useState
- [ ] useFormStatus is called in a child component of the form
- [ ] useOptimistic is not used for critical business operations (payments, etc.)
- [ ] Server Action is correctly marked 'use server'

### Suspense & Streaming

- [ ] Suspense boundaries are split according to UX needs
- [ ] Every Suspense has a matching Error Boundary
- [ ] A meaningful fallback is provided (skeleton screen > Spinner)
- [ ] Avoid awaiting slow data at the layout level

### TanStack Query

- [ ] queryKey includes every parameter that affects the data
- [ ] A reasonable staleTime is set (not the default 0)
- [ ] useSuspenseQuery does not use enabled
- [ ] Related queries are invalidated after a Mutation succeeds
- [ ] isPending vs isLoading difference is understood
