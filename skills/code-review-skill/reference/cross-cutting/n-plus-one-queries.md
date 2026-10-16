# N+1 Query Problem — Cross-Language Guide

> N+1 queries are the most common performance anti-pattern in ORM and database access layers. This document covers the problem definition, detection methods, general solutions, and cross-language code examples.

## Contents

- [Problem Definition](#problem-definition)
- [Performance Impact](#performance-impact)
- [Detection Methods](#detection-methods)
- [General Solutions](#general-solutions)
- [Language-Specific Implementations](#language-specific-implementations)
- [Review Checklist](#review-checklist)

---

## Problem Definition

N+1 queries occur when **1 query fetches N records, then a loop triggers N additional queries** to fetch related data.

```
Request flow:
  1 query   → fetch N parent records
  N queries → one query per parent record for related data
  ─────────
  Total: 1 + N queries
```

### Consequences

| Problem | Impact |
|------|------|
| **Query count grows linearly** | 100 records = 101 SQL queries, 1000 = 1001 |
| **Network latency adds up** | Every query pays round-trip latency (RTT), N round trips >> 1 batch query |
| **Connection pool exhaustion** | Large numbers of queries occupy all database connections and slow down the whole application |
| **Hard to spot in development** | Dev environments have little data, so N+1 is not obvious; performance collapses at production data volumes |

---

## Performance Impact

### Scenario Comparison: Fetching 100 Users and Their Orders

| Approach | SQL count | Latency (assuming RTT=1ms) | Suitable for |
|------|----------|---------------------|---------|
| N+1 lazy loading | 101 queries | ~101ms | Very small data volume |
| Eager loading (JOIN) | 1 query | ~1ms | One-to-many, moderate data volume |
| Eager loading (IN) | 2 queries | ~2ms | Many-to-many, large data sets |
| DataLoader / batch | 2 queries | ~2ms | GraphQL / complex graph queries |

### SQL Count Comparison

```sql
-- ❌ N+1: 1 + 100 = 101 queries
SELECT * FROM users;                          -- 1 query
SELECT * FROM orders WHERE user_id = 1;       -- query 2
SELECT * FROM orders WHERE user_id = 2;       -- query 3
...
SELECT * FROM orders WHERE user_id = 100;     -- query 101

-- ✅ Batch: 2 queries
SELECT * FROM users;
SELECT * FROM orders WHERE user_id IN (1,2,...,100);
```

---

## Detection Methods

### 1. ORM SQL Logging

Enable SQL logging and watch the query count in test or development environments:

```python
# Django
import logging
logging.getLogger('django.db.backends').setLevel(logging.DEBUG)

# SQLAlchemy
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

```java
// Spring Boot application.yml
spring:
  jpa:
    show-sql: true
    properties:
      hibernate.format_sql: true
```

```csharp
// EF Core
optionsBuilder.LogTo(Console.WriteLine, LogLevel.Information);
```

### 2. Query Count Assertions

Assert the number of SQL queries in tests:

```python
# Django: django-assert-num-queries
from django.test.utils import CaptureQueriesContext
from django.db import connection

with CaptureQueriesContext(connection) as ctx:
    list(User.objects.select_related("profile").all())
assert len(ctx) <= 2  # expect at most 2 queries
```

```java
// Hibernate: p6spy or datasource-proxy
// count SQL executions in tests
assertThat(sqlCount).isLessThanOrEqualTo(2);
```

### 3. APM / Database Monitoring Tools

- **Django Debug Toolbar** — shows SQL count and time in real time
- **p6spy** (Java) — JDBC layer interception, logs all SQL
- **MiniProfiler** (.NET) — in-page SQL statistics
- **DataDog / New Relic** — slow query alerts in production

---

## General Solutions

### Solution 1: Eager Loading (JOIN Preloading)

Fetch the parent and related records in a single JOIN query. Suitable for one-to-one and one-to-many.

### Solution 2: Batch Fetching (IN Clause Query)

Two queries: the parent records + `WHERE id IN (...)` to fetch the related records in bulk. Suitable for many-to-many and large data sets.

### Solution 3: DataLoader Pattern

In GraphQL or complex graph query scenarios, collect every ID needed and combine them into a single batch query.

```
// DataLoader pseudocode
class DataLoader<K, V> {
    load(K key) → V         // registers the request, does not query immediately
    loadAll([K]) → [V]      // merges into a single batch query
}
```

### Solution 4: Projection

Query only the fields you need to reduce the amount of data transferred:

```sql
-- ❌ Fetches all columns
SELECT * FROM users JOIN profiles ON ...

-- ✅ Project only the fields needed
SELECT u.name, p.avatar_url FROM users u JOIN profiles p ON ...
```

---

## Language-Specific Implementations

### Python / Django


```python
# ForeignKey / OneToOne → select_related (SQL JOIN)
books = Book.objects.select_related("publisher")

# M2M / reverse FK → prefetch_related (2 queries + Python merge)
authors = Author.objects.prefetch_related("books")

# Nested prefetching
authors = Author.objects.prefetch_related("books__publisher")

# Prefetch objects for fine-grained control
from django.db.models import Prefetch
authors = Author.objects.prefetch_related(
    Prefetch("books", queryset=Book.objects.filter(published=True), to_attr="published_books")
)
```

### Python / SQLAlchemy (FastAPI)


```python
from sqlalchemy.orm import selectinload

# selectinload: IN clause batch loading (recommended for async scenarios)
stmt = select(Order).options(selectinload(Order.customer))

# joinedload: JOIN loading
stmt = select(Order).options(joinedload(Order.customer))
```

### Java / JPA (Spring Boot)


```java
// ❌ FetchType.EAGER or lazy loading triggered inside a loop
@OneToMany(fetch = FetchType.EAGER)  // dangerous!

// ✅ JOIN FETCH
@Query("SELECT u FROM User u JOIN FETCH u.orders")
List<User> findAllWithOrders();

// ✅ @EntityGraph (declarative)
@EntityGraph(attributePaths = {"orders", "profile"})
List<User> findAll();

// ✅ @BatchSize (reduces N+1 to N/batchSize + 1)
@OneToMany
@BatchSize(size = 50)
private List<Order> orders;
```

### C# / EF Core


```csharp
// ❌ N+1: foreach triggers lazy loading
foreach (var blog in await context.Blogs.ToListAsync())
    foreach (var post in blog.Posts)  // queries on every iteration!

// ✅ Include + ThenInclude
var blogs = await context.Blogs
    .Include(b => b.Posts)
    .ToListAsync();

// ✅ Projection (safest, avoids over-fetching)
var data = await context.Blogs
    .Select(b => new { b.Url, PostTitles = b.Posts.Select(p => p.Title) })
    .ToListAsync();
```

### PHP / Laravel / Doctrine


```php
// ❌ Query inside a loop
foreach ($orders as $order) {
    $customer = $customerRepo->find($order->customerId);
    render($order, $customer);
}

// ✅ Batch preloading
$customerIds = array_unique(array_map(fn($o) => $o->customerId, $orders));
$customers = $customerRepo->findByIds($customerIds);

foreach ($orders as $order) {
    render($order, $customers[$order->customerId] ?? null);
}

// Laravel Eloquent: with()
$orders = Order::with('customer')->get();

// Doctrine: JOIN FETCH
$dql = 'SELECT o, c FROM Order o JOIN o.customer c';
```

### TypeScript / Prisma

```typescript
// ❌ N+1
const users = await prisma.user.findMany();
for (const user of users) {
    user.posts = await prisma.post.findMany({ where: { userId: user.id } });
}

// ✅ include (Prisma generates a JOIN or batch queries automatically)
const users = await prisma.user.findMany({
    include: { posts: true },
});

// ✅ Nested include
const users = await prisma.user.findMany({
    include: {
        posts: {
            include: { comments: true },
        },
    },
});
```

---

## Review Checklist

### Detection
- [ ] SQL logging or query count monitoring is enabled
- [ ] Tests include query count assertions
- [ ] APM tooling has N+1 alerts configured

### Fixes
- [ ] ForeignKey / OneToOne relations use JOIN eager loading
- [ ] M2M / reverse relations use IN batch preloading
- [ ] Avoid triggering database queries inside loops
- [ ] Use projection to fetch only the fields needed

### Architecture
- [ ] List API is paginated to avoid loading too many records at once
- [ ] GraphQL scenarios use DataLoader
- [ ] A caching strategy (Redis) handles frequently read related data
