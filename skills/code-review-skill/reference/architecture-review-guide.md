# Architecture Review Guide

A guide to reviewing architecture design, helping assess whether the code's architecture is sound and its design appropriate.

## SOLID Principles Checklist

### S - Single Responsibility Principle (SRP)

**Key checks:**
- Does this class/module have only one reason to change?
- Do all methods in the class serve the same purpose?
- Can this class be explained to a non-technical person in one sentence?

**Signs to look for in code review:**
```
⚠️ Class name contains generic words such as "And", "Manager", "Handler", "Processor"
⚠️ A class exceeds 200-300 lines of code
⚠️ A class has more than 5-7 public methods
⚠️ Different methods operate on completely different data
```

**Review questions:**
- "What is this class responsible for? Can it be split?"
- "If requirement X changes, which methods need to change? What if requirement Y changes?"

### O - Open/Closed Principle (OCP)

**Key checks:**
- Does adding a new feature require modifying existing code?
- Can new behavior be added through extension (inheritance, composition)?
- Are there many if/else or switch statements handling different types?

**Signs to look for in code review:**
```
⚠️ switch/if-else chains handling different types
⚠️ Adding a feature requires modifying core classes
⚠️ Type checks (instanceof, typeof) scattered across the code
```

**Review questions:**
- "If a new type X is added, which files need to change?"
- "Will this switch statement grow as new types are added?"

### L - Liskov Substitution Principle (LSP)

**Key checks:**
- Can a subclass fully replace its parent class?
- Does a subclass change the expected behavior of parent class methods?
- Does any subclass throw exceptions the parent class does not declare?

**Signs to look for in code review:**
```
⚠️ Explicit type conversion (casting)
⚠️ Subclass method throws NotImplementedException
⚠️ Subclass method has an empty implementation or only a return
⚠️ Code using the base class has to check the concrete type
```

**Review questions:**
- "If a subclass replaces the parent class, does the calling code need to change?"
- "Does this method's behavior in the subclass match the parent class's contract?"

### I - Interface Segregation Principle (ISP)

**Key checks:**
- Is the interface small and focused enough?
- Are implementing classes forced to implement methods they do not need?
- Do clients depend on methods they do not use?

**Signs to look for in code review:**
```
⚠️ Interface has more than 5-7 methods
⚠️ Implementing class has empty methods or throws NotImplementedException
⚠️ Interface name is too broad (IManager, IService)
⚠️ Different clients use only some of the interface's methods
```

**Review questions:**
- "Is every method of this interface used by every implementing class?"
- "Can this large interface be split into smaller, purpose-specific interfaces?"

### D - Dependency Inversion Principle (DIP)

**Key checks:**
- Do high-level modules depend on abstractions rather than concrete implementations?
- Is dependency injection used instead of creating objects directly with new?
- Are abstractions defined by high-level modules rather than low-level ones?

**Signs to look for in code review:**
```
⚠️ High-level module directly instantiates concrete low-level classes with new
⚠️ Imports concrete implementation classes instead of interfaces/abstract classes
⚠️ Configuration and connection strings hardcoded in business logic
⚠️ Hard to write unit tests for a class
```

**Review questions:**
- "Can this class's dependencies be replaced by a mock in tests?"
- "If the database/API implementation is replaced, how many places need to change?"

---

## Identifying Architecture Anti-Patterns

### Critical Anti-Patterns

| Anti-pattern | Signs | Impact |
|--------|----------|------|
| **Big Ball of Mud** | No clear module boundaries; any code may call any other code | Hard to understand, modify, and test |
| **God Object** | A single class takes on too many responsibilities, knows too much and does too much | High coupling; hard to reuse and test |
| **Spaghetti Code** | Tangled control flow, goto or deep nesting, hard to trace execution paths | Hard to understand and maintain |
| **Lava Flow** | Ancient code nobody dares to touch, lacking documentation and tests | Technical debt accumulates |

### Design Anti-Patterns

| Anti-pattern | Signs | Recommendation |
|--------|----------|------|
| **Golden Hammer** | Using the same technology/pattern for every problem | Choose the solution that fits the problem |
| **Over-engineering (Gas Factory)** | Simple problems solved with complex solutions, overuse of design patterns | YAGNI principle: start simple, add complexity later |
| **Boat Anchor** | Unused code written because it "might be needed in the future" | Delete unused code; write it when needed |
| **Copy-Paste Programming** | The same logic appears in multiple places | Extract a shared method or module |

### Review Questions

```markdown
🔴 [blocking] "This class has 2000 lines of code; consider splitting it into several focused classes"
🟡 [important] "This logic is repeated in 3 places. Consider extracting it into a shared method?"
💡 [suggestion] "This switch statement can be replaced with the Strategy pattern, which is easier to extend"
```

---

## Coupling and Cohesion Assessment

### Coupling Types (best to worst)

| Type | Description | Example |
|------|------|------|
| **Message Coupling** ✅ | Data passed through parameters | `calculate(price, quantity)` |
| **Data Coupling** ✅ | Sharing simple data structures | `processOrder(orderDTO)` |
| **Stamp Coupling** ⚠️ | Sharing a complex data structure but using only part of it | Passing a whole User object but using only name |
| **Control Coupling** ⚠️ | Passing a control flag that changes behavior | `process(data, isAdmin=true)` |
| **Common Coupling** ❌ | Sharing global variables | Multiple modules read and write the same global state |
| **Content Coupling** ❌ | Directly accessing another module's internals | Directly manipulating another class's private properties |

### Cohesion Types (best to worst)

| Type | Description | Quality |
|------|------|------|
| **Functional Cohesion** | All elements perform a single task | ✅ Best |
| **Sequential Cohesion** | Output of one step is input to the next | ✅ Good |
| **Communicational Cohesion** | Operate on the same data | ⚠️ Acceptable |
| **Temporal Cohesion** | Tasks executed at the same time | ⚠️ Weak |
| **Logical Cohesion** | Logically related but functionally different | ❌ Poor |
| **Coincidental Cohesion** | No obvious relationship | ❌ Worst |

### Metrics Reference

```yaml
Coupling metrics:
  CBO (Coupling Between Objects):
    Good: < 5
    Warning: 5-10
    Danger: > 10

  Ce (Efferent Coupling):
    Description: number of external classes it depends on
    Good: < 7

  Ca (Afferent Coupling):
    Description: number of classes that depend on it
    High value means: changes have wide impact, must stay stable

Cohesion metrics:
  LCOM4 (Lack of Cohesion of Methods):
    1: Single responsibility ✅
    2-3: May need splitting ⚠️
    >3: Should be split ❌
```

### Review Questions

- "How many other modules does this module depend on? Can that be reduced?"
- "How many other places will a change to this class affect?"
- "Do all methods of this class operate on the same data?"

---

## Layered Architecture Review

### Clean Architecture Layer Check

```
┌─────────────────────────────────────┐
│         Frameworks & Drivers        │ ← Outermost: Web, DB, UI
├─────────────────────────────────────┤
│         Interface Adapters          │ ← Controllers, Gateways, Presenters
├─────────────────────────────────────┤
│          Application Layer          │ ← Use Cases, Application Services
├─────────────────────────────────────┤
│            Domain Layer             │ ← Entities, Domain Services
└─────────────────────────────────────┘
          ↑ Dependencies can only point inward ↑
```

### Dependency Rule Check

**Core rule: source code dependencies can only point to inner layers**

```typescript
// ❌ Violates the dependency rule: Domain layer depends on Infrastructure
// domain/User.ts
import { MySQLConnection } from '../infrastructure/database';

// ✅ Correct: Domain layer defines the interface, Infrastructure implements it
// domain/UserRepository.ts (interface)
interface UserRepository {
  findById(id: string): Promise<User>;
}

// infrastructure/MySQLUserRepository.ts (implementation)
class MySQLUserRepository implements UserRepository {
  findById(id: string): Promise<User> { /* ... */ }
}
```

### Review Checklist

**Layer boundary checks:**
- [ ] Does the Domain layer have external dependencies (database, HTTP, file system)?
- [ ] Does the Application layer access the database or call an external API directly?
- [ ] Does the Controller contain business logic?
- [ ] Are there cross-layer calls (UI calling the Repository directly)?

**Separation of concerns checks:**
- [ ] Is business logic separated from presentation logic?
- [ ] Is data access encapsulated in a dedicated layer?
- [ ] Is configuration and environment-related code managed in one place?

### Review Questions

```markdown
🔴 [blocking] "The Domain entity imports the database connection directly, violating the dependency rule"
🟡 [important] "The Controller contains business calculation logic; consider moving it to the Service layer"
💡 [suggestion] "Consider using dependency injection to decouple these components"
```

---

## Design Pattern Usage Assessment

### When to Use Design Patterns

| Pattern | Use when | Avoid when |
|------|----------|------------|
| **Factory** | Objects of different types must be created, with the type determined at runtime | Only one type, or the type is fixed |
| **Strategy** | The algorithm must be switched at runtime; there are several interchangeable behaviors | Only one algorithm, or the algorithm never changes |
| **Observer** | One-to-many dependency; a state change must notify multiple objects | A simple direct call is enough |
| **Singleton** | A single global instance is truly needed, e.g. configuration management | Objects that can be passed in through dependency injection |
| **Decorator** | Responsibilities must be added dynamically, avoiding subclass explosion | Responsibilities are fixed; no dynamic composition is needed |

### Over-Engineering Warning Signs

```
⚠️ Patternitis (pattern overuse) warning signs:

1. A simple if/else is replaced with Strategy pattern + factory + registry
2. An interface with only one implementation
3. Abstraction layers added because they "might be needed in the future"
4. Lines of code increase sharply because of applied patterns
5. Newcomers need a long time to understand the code structure
```

### Review Principles

```markdown
✅ Using patterns correctly:
- Solves a real extensibility problem
- Code is easier to understand and test
- Adding new features becomes simpler

❌ Overusing patterns:
- Using a pattern for its own sake
- Adds unnecessary complexity
- Violates the YAGNI principle
```

### Review Questions

- "What specific problem does this pattern solve?"
- "Without this pattern, what problems would the code have?"
- "Does the value this abstraction layer brings outweigh its complexity?"

---

## Extensibility and Scalability Assessment

### Extensibility and Scalability Checklist

**Feature extensibility:**
- [ ] Does adding a new feature require changing core code?
- [ ] Are extension points provided (hooks, plugins, events)?
- [ ] Is configuration externalized (config files, environment variables)?

**Data scalability:**
- [ ] Does the data model support adding new fields?
- [ ] Has data volume growth been considered?
- [ ] Do queries have suitable indexes?

**Load scalability:**
- [ ] Can it scale horizontally (by adding more instances)?
- [ ] Are there stateful dependencies (session, local cache)?
- [ ] Do database connections use a connection pool?

### Extension Point Design Check

```typescript
// ✅ Good extension design: use events/hooks
class OrderService {
  private hooks: OrderHooks;

  async createOrder(order: Order) {
    await this.hooks.beforeCreate?.(order);
    const result = await this.save(order);
    await this.hooks.afterCreate?.(result);
    return result;
  }
}

// ❌ Bad extension design: all behavior hardcoded
class OrderService {
  async createOrder(order: Order) {
    await this.sendEmail(order);        // hardcoded
    await this.updateInventory(order);  // hardcoded
    await this.notifyWarehouse(order);  // hardcoded
    return await this.save(order);
  }
}
```

### Review Questions

```markdown
💡 [suggestion] "If a new payment method must be supported in the future, is this design easy to extend?"
🟡 [important] "The logic here is hardcoded; consider using configuration or the Strategy pattern?"
📚 [learning] "Event-driven architecture can make this feature easier to extend"
```

---

## Code Structure Best Practices

### Directory Organization

**Organize by feature/domain (recommended):**
```
src/
├── user/
│   ├── User.ts           (entity)
│   ├── UserService.ts    (service)
│   ├── UserRepository.ts (data access)
│   └── UserController.ts (API)
├── order/
│   ├── Order.ts
│   ├── OrderService.ts
│   └── ...
└── shared/
    ├── utils/
    └── types/
```

**Organize by technical layer (not recommended):**
```
src/
├── controllers/     ← different domains mixed together
│   ├── UserController.ts
│   └── OrderController.ts
├── services/
├── repositories/
└── models/
```

### Naming Convention Check

| Type | Convention | Example |
|------|------|------|
| Class name | PascalCase, noun | `UserService`, `OrderRepository` |
| Method name | camelCase, verb | `createUser`, `findOrderById` |
| Interface name | I prefix or no prefix | `IUserService` or `UserService` |
| Constant | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| Private property | Underscore prefix or none | `_cache` or `#cache` |

### File Size Guidelines

```yaml
Recommended limits:
  Single file: < 300 lines
  Single function: < 50 lines
  Single class: < 200 lines
  Function parameters: < 4
  Nesting depth: < 4 levels

When limits are exceeded:
  - Consider splitting into smaller units
  - Use composition instead of inheritance
  - Extract helper functions or classes
```

### Review Questions

```markdown
🟢 [nit] "This 500-line file could be split by responsibility"
🟡 [important] "Consider organizing the directory structure by feature domain rather than by technical layer"
💡 [suggestion] "The function name `process` is not clear enough; consider renaming it to `calculateOrderTotal`?"
```

---

## Quick Reference Checklist

### 5-Minute Architecture Review Quick Check

```markdown
□ Is the dependency direction correct? (outer layers depend on inner layers)
□ Are there circular dependencies?
□ Is the core business logic decoupled from the framework/UI/database?
□ Are SOLID principles followed?
□ Are there obvious anti-patterns?
```

### Red Flags (must address)

```markdown
🔴 God Object - a single class exceeds 1000 lines
🔴 Circular dependency - A → B → C → A
🔴 Domain layer contains framework dependencies
🔴 Hardcoded configuration and secrets
🔴 External service calls without an interface
```

### Yellow Flags (should address)

```markdown
🟡 Coupling between classes (CBO) > 10
🟡 More than 5 method parameters
🟡 Nesting deeper than 4 levels
🟡 Duplicated code block > 10 lines
🟡 Interface with only one implementation
```

---

## Recommended Tools

| Tool | Purpose | Language support |
|------|------|----------|
| **SonarQube** | Code quality, coupling analysis | Multiple languages |
| **NDepend** | Dependency analysis, architecture rules | .NET |
| **JDepend** | Package dependency analysis | Java |
| **Madge** | Module dependency graph | JavaScript/TypeScript |
| **ESLint** | Code style, complexity checks | JavaScript/TypeScript |
| **CodeScene** | Technical debt, hotspot analysis | Multiple languages |

---

## References

- [Clean Architecture - Uncle Bob](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [SOLID Principles in Code Review - JetBrains](https://blog.jetbrains.com/upsource/2015/08/31/what-to-look-for-in-a-code-review-solid-principles-2/)
- [Software Architecture Anti-Patterns](https://medium.com/@christophnissle/anti-patterns-in-software-architecture-3c8970c9c4f5)
- [Coupling and Cohesion in System Design](https://www.geeksforgeeks.org/system-design/coupling-and-cohesion-in-system-design/)
- [Design Patterns - Refactoring Guru](https://refactoring.guru/design-patterns)
