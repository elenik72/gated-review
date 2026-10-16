# Universal Code Quality Anti-Patterns

> Language-agnostic guide to code quality anti-patterns, covering code reuse, leaky abstractions, parameter sprawl, nested conditionals, stringly-typed code, TOCTOU, no-op updates, and other core topics. Applies to PR reviews in any language.

## Contents

- [Code Reuse Review](#code-reuse-review)
- [Parameter Sprawl](#parameter-sprawl)
- [Leaky Abstraction](#leaky-abstraction)
- [Stringly-Typed Code](#stringly-typed-code)
- [Nested Conditional Expressions](#nested-conditional-expressions)
- [Copy-Paste Variants](#copy-paste-variants)
- [No-Op Updates](#no-op-updates)
- [TOCTOU Race Conditions](#toctou-race-conditions)
- [Overly Broad Operations](#overly-broad-operations)
- [Redundant State](#redundant-state)
- [General Quality Review Checklist](#general-quality-review-checklist)

---

## Code Reuse Review

Before accepting new code, search the existing codebase for reusable utilities.

### Search for Existing Utilities

```python
# ❌ New path-joining logic - the project already has PathBuilder
def get_config_path(name):
    base = os.environ.get("APP_ROOT", ".")
    return os.path.join(base, "config", name + ".json")

# ✅ Use the existing PathBuilder
def get_config_path(name):
    return PathBuilder.config(f"{name}.json")
```

```javascript
// ❌ Hand-written debounce - the project already has lodash or utils/debounce.ts
function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

// ✅ Use the existing utility
import { debounce } from "@/utils/debounce";
```

**Review points:**
- Does the new function duplicate the name or functionality of an existing utility?
- Can the inline logic be replaced by a call to an existing module?
- Check neighboring files and the shared/utils directories

---

## Parameter Sprawl

### Ever-Growing Function Parameters

```python
# ❌ Add one more parameter for each new requirement
def create_user(name, email, role, team, active, avatar_url, timezone):
    ...

# ✅ Use a config object / dataclass
@dataclass
class CreateUserParams:
    name: str
    email: str
    role: Role = Role.MEMBER
    team: str | None = None
    active: bool = True
    avatar_url: str | None = None
    timezone: str = "UTC"

def create_user(params: CreateUserParams) -> User:
    ...
```

```typescript
// ❌ 6+ positional parameters
function renderWidget(
  title: string, width: number, height: number,
  theme: string, collapsible: boolean, icon: string
) { ... }

// ✅ Options object pattern
interface WidgetOptions {
  title: string;
  width?: number;
  height?: number;
  theme?: "light" | "dark";
  collapsible?: boolean;
  icon?: string;
}
function renderWidget(options: WidgetOptions) { ... }
```

**Review points:**
- Does the function take ≥ 4 parameters? Consider an options object / dataclass
- Is the new parameter just a boolean flag? Consider an enum or strategy pattern
- Are there mutually exclusive parameters like `enable_x`, `disable_y`?

---

## Leaky Abstraction

### Exposing Internal Implementation Details

```python
# ❌ Returns an internal ORM object - callers are forced to know SQLAlchemy
def get_users():
    return session.query(User).filter(User.active == True).all()

# ✅ Return a domain object, hiding the persistence layer
def get_active_users() -> list[UserDTO]:
    rows = user_repo.find_active()
    return [UserDTO.from_row(r) for r in rows]
```

```typescript
// ❌ Component receives the raw API response structure
<UserCard user={apiResponse.data.results[0]} />

// ✅ Component receives a domain type; an adapter handles the mapping
interface UserSummary {
  displayName: string;
  avatarUrl: string;
}
<UserCard user={adaptUser(apiResponse)} />
```

**Review points:**
- Does the return type leak the underlying implementation (ORM, HTTP client, file format)?
- Does the component/function depend on an external system's data structures?
- Does it break an existing abstraction boundary?

---

## Stringly-Typed Code

### Raw Strings Instead of Constants/Enums

```python
# ❌ Magic strings scattered everywhere
if status == "active":
    ...
if role == "admin":
    ...

# ✅ Use an enum
class Status(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"

if user.status == Status.ACTIVE:
    ...
```

```typescript
// ❌ Raw string event names - a typo raises no error
emitter.emit("userCreated", data);
emitter.on("usercreated", handler); // bug: typo

// ✅ Constants or a branded type
const Events = {
  USER_CREATED: "userCreated",
  USER_SUSPENDED: "userSuspended",
} as const;
emitter.emit(Events.USER_CREATED, data);
```

**Review points:**
- Is a string used in place of an existing enum/union type?
- Are event names, action types, and status values scattered across multiple files?
- Are string comparisons case-sensitive but not validated?

---

## Nested Conditional Expressions

### Ternary Chains and Nested if/else

```python
# ❌ Ternary chain is hard to read
label = (
    "Admin" if role == "admin" else
    "Manager" if role == "manager" else
    "Viewer" if role == "viewer" else
    "Unknown"
)

# ✅ Lookup table or match
ROLE_LABELS = {
    "admin": "Admin",
    "manager": "Manager",
    "viewer": "Viewer",
}
label = ROLE_LABELS.get(role, "Unknown")
```

```typescript
// ❌ Nested ternary
const bg = isHovered
  ? isSelected ? "blue" : "gray"
  : isSelected ? "navy" : "white";

// ✅ Lookup map
const bgMap: Record<string, string> = {
  "true-true": "blue",
  "true-false": "gray",
  "false-true": "navy",
  "false-false": "white",
};
const bg = bgMap[`${isHovered}-${isSelected}`];
```

```python
# ❌ Nested if, 3+ levels deep
def process(order):
    if order is not None:
        if order.items:
            for item in order.items:
                if item.price > 0:
                    ...

# ✅ Early return + guard clauses
def process(order):
    if not order or not order.items:
        return
    for item in order.items:
        if item.price <= 0:
            continue
        ...
```

**Review points:**
- Are ternary expressions nested ≥ 2 levels deep?
- Is if/else nesting ≥ 3 levels deep?
- Can it be replaced with a lookup table, early return, or match?

---

## Copy-Paste Variants

### Near-Duplicate Code Blocks

```python
# ❌ Two near-identical functions that differ only in field names
def format_user(user):
    return f"{user.first_name} {user.last_name} ({user.email})"

def format_employee(emp):
    return f"{emp.first_name} {emp.last_name} ({emp.work_email})"

# ✅ Unified abstraction
def format_person(first: str, last: str, email: str) -> str:
    return f"{first} {last} ({email})"
```

```typescript
// ❌ Copy-paste handler with only the URL changed
async function deletePost(id: string) {
  await fetch(`/api/posts/${id}`, { method: "DELETE" });
  router.push("/posts");
}
async function deleteComment(id: string) {
  await fetch(`/api/comments/${id}`, { method: "DELETE" });
  router.push("/comments");
}

// ✅ Parameterized
async function deleteResource(resource: string, id: string) {
  await fetch(`/api/${resource}/${id}`, { method: "DELETE" });
  router.push(`/${resource}`);
}
```

**Review points:**
- Are there ≥ 2 code blocks that differ only in variable names/URLs/strings?
- Can a parameterized shared function be extracted?
- Can a template method or strategy eliminate the variants?

---

## No-Op Updates

### Unconditional State Updates

```typescript
// ❌ Triggers an update on every poll - even when the data is unchanged
useEffect(() => {
  const interval = setInterval(() => {
    fetch("/api/status").then(r => r.json()).then(setStatus);
  }, 5000);
  return () => clearInterval(interval);
}, []);

// ✅ Update only when the value changes
useEffect(() => {
  const interval = setInterval(() => {
    fetch("/api/status")
      .then(r => r.json())
      .then(data => {
        setStatus(prev => isEqual(prev, data) ? prev : data);
      });
  }, 5000);
  return () => clearInterval(interval);
}, []);
```

```python
# ❌ Writes to the DB on every loop - even when the value is unchanged
for item in items:
    item.status = compute_status(item)
    session.commit()

# ✅ Write only on change
for item in items:
    new_status = compute_status(item)
    if item.status != new_status:
        item.status = new_status
        session.commit()
```

**Review points:**
- Do polling / interval / event handlers update unconditionally?
- Does the wrapper function honor same-reference returns?
- Do DB writes check for an actual change?

---

## TOCTOU Race Conditions

### Time-of-Check-to-Time-of-Use

```python
# ❌ Check first, then operate - the file may be deleted/created in between
if os.path.exists(path):
    with open(path) as f:
        data = f.read()

# ✅ Operate directly + handle the exception
try:
    with open(path) as f:
        data = f.read()
except FileNotFoundError:
    data = None
```

```python
# ❌ Check balance → deduct: the two steps are not atomic
if account.balance >= amount:
    account.balance -= amount

# ✅ Atomic operation or lock
with account.lock:
    if account.balance < amount:
        raise InsufficientFundsError()
    account.balance -= amount
```

```typescript
// ❌ Check-then-act is unsafe in async code
if (!fileExists(path)) {
  await writeFile(path, content);
}

// ✅ Operate directly + catch
try {
  await writeFile(path, content, { flag: "wx" });
} catch (e) {
  if (e.code === "EEXIST") { /* handle */ }
  else throw e;
}
```

**Review points:**
- Can the `if exists → operate` pattern be replaced with `try operate → catch`?
- Are multi-step state changes inside a transaction/lock?
- In async code, is there an await between the check and the act?

---

## Overly Broad Operations

### Reading Too Much Data

```python
# ❌ Reads the whole file, then takes the first line
content = Path("log.txt").read_text()
first_line = content.split("\n")[0]

# ✅ Read only the first line, without loading the whole file
with open("log.txt") as f:
    first_line = f.readline()
```

```typescript
// ❌ Loads all items, then filters
const allItems = await db.query("SELECT * FROM orders");
const pending = allItems.filter(o => o.status === "pending");

// ✅ Filter at the database layer
const pending = await db.query(
  "SELECT * FROM orders WHERE status = ?", ["pending"]
);
```

```python
# ❌ Reads the whole list to find one record
users = list(User.objects.all())
user = next(u for u in users if u.id == user_id)

# ✅ Precise query
user = User.objects.get(id=user_id)
```

**Review points:**
- Is a whole collection/file read when only a small part is used?
- Can filtering be pushed down to the database/storage layer?
- Does the API call support pagination/limit parameters?

---

## Redundant State

### State That Can Be Derived

```typescript
// ❌ Stores fullName alongside firstName + lastName
interface User {
  firstName: string;
  lastName: string;
  fullName: string;  // redundant
}

// ✅ fullName is a derived value
interface User {
  firstName: string;
  lastName: string;
}
const fullName = `${user.firstName} ${user.lastName}`;
```

```python
# ❌ Cached values can go stale when the source data changes
class Order:
    total: float
    item_count: int       # redundant if len(items) gives the same
    items: list[Item]

# ✅ Derive it or use a property
class Order:
    items: list[Item]

    @property
    def total(self) -> float:
        return sum(item.price for item in self.items)

    @property
    def item_count(self) -> int:
        return len(self.items)
```

**Review points:**
- Can any field be derived from other fields?
- Do cached values have an invalidation mechanism?
- Can the observer/effect be replaced with a direct call?

---

## General Quality Review Checklist

- [ ] **Reuse review**: Searched for an existing utility/helper instead of reinventing the wheel?
- [ ] **Parameter count**: Functions take ≤ 3 parameters? If more, use an options object / dataclass?
- [ ] **Abstraction boundaries**: Return types do not expose internal implementation details (ORM, HTTP client, file format)?
- [ ] **Type safety**: No magic strings in place of an existing enum/constant/union type?
- [ ] **Conditional depth**: Ternary nesting ≤ 1 level? if/else nesting ≤ 2 levels?
- [ ] **DRY**: No copy-paste-with-variation (≥ 2 near-identical code blocks)?
- [ ] **No-op guard**: Polling / interval / event handlers have a change-detection guard?
- [ ] **TOCTOU**: `if exists → operate` replaced with `try operate → catch`?
- [ ] **Read scope**: No reading of a whole collection/file just to use a subset?
- [ ] **Redundant state**: No stored fields that can be derived from other fields?
