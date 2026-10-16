# Error Handling Principles — Cross-Language Guide

> This document covers the core principles of error handling, common anti-patterns, error hierarchy design, and logging best practices. Each principle comes with cross-language code examples.

## Contents

- [Core Principles](#core-principles)
- [Anti-Patterns](#anti-patterns)
- [Error Hierarchy Design](#error-hierarchy-design)
- [Logging Best Practices](#logging-best-practices)
- [Cross-Language Code Examples](#cross-language-code-examples)
- [Review Checklist](#review-checklist)

---

## Core Principles

### Principle 1: Do Not Swallow Errors

Every error must be handled: propagate it, log it, or convert it to a more meaningful error. **Never** ignore it silently.

```
// Pseudocode
result = risky_operation()
if error:
    // Must do one of the following:
    //   1. return error to caller (propagate)
    //   2. log + return fallback (graceful degradation)
    //   3. panic/crash (when unrecoverable)
```

### Principle 2: Add Context

Error messages should include the **operation description** and **key parameters**, so the problem can be located without reading the call chain.

```
// ❌ No context
"failed"

// ✅ With context
"failed to process order #12345: payment gateway timeout after 30s"
```

### Principle 3: Use Specific Error Types

Use error types to distinguish failure causes, so callers can handle each failure scenario precisely.

```
// ❌ Generic error
throw new Error("something went wrong")

// ✅ Specific type
throw new OrderNotFoundError(orderId)
throw new PaymentTimeoutException(gatewayName, timeoutMs)
```

### Principle 4: Fail Fast

Validate preconditions before the operation starts and fail as early as possible. This avoids inconsistent state caused by discovering an error only after partial execution.

```
// ❌ Invalid argument discovered only halfway through execution
def process(data, config):
    result = expensive_computation(data)  # 5 seconds already spent
    if not config.valid:
        raise ValueError("invalid config")  # 5 seconds wasted

// ✅ Validate first
def process(data, config):
    if not config.valid:
        raise ValueError("invalid config")
    result = expensive_computation(data)
```

### Principle 5: Handle Each Error Only Once

Do not handle the same error at every layer (log, return, and wrap all at once). Pick one approach and let the caller decide how to handle it.

```
// ❌ Both log and return (duplicate handling)
if err:
    log.error("failed: %s", err)
    return err

// ✅ Only wrap and return; let the top level handle it in one place
if err:
    return wrap_error("operation failed", err)
```

---

## Anti-Patterns

### Anti-Pattern 1: Empty catch Block

```python
# ❌ Python: empty except swallows all exceptions (including KeyboardInterrupt)
try:
    result = risky()
except:
    pass

# ❌ Java: empty catch swallows the exception
try {
    result = risky();
} catch (Exception e) {
    // do nothing
}

# ❌ Go: ignores the error
result, _ := risky()

# ❌ Rust: unwrap() in production code
let result = risky().unwrap();  // panic on error
```

### Anti-Pattern 2: Overly Broad catch

```python
# ❌ Catches all exceptions, cannot distinguish failure types
try:
    result = risky()
except Exception as e:
    logger.error(f"failed: {e}")

# ✅ Catch specific exceptions
try:
    result = risky()
except ConnectionError as e:
    logger.warning(f"network issue, retrying: {e}")
    result = retry(risky)
except ValueError as e:
    logger.error(f"bad input: {e}")
    raise
```

### Anti-Pattern 3: Losing the Original Exception

```python
# ❌ Loses the original exception's stack trace and details
try:
    result = external_api.call()
except APIError as e:
    raise RuntimeError("API failed")  # cause is lost

# ✅ Preserve the exception chain
try:
    result = external_api.call()
except APIError as e:
    raise RuntimeError("API failed") from e
```

```java
// ❌ Loses the original exception
catch (IOException e) {
    throw new ServiceException("IO failed");
}

// ✅ Preserves the cause
catch (IOException e) {
    throw new ServiceException("IO failed", e);
}
```

### Anti-Pattern 4: Using Exceptions for Flow Control

```python
# ❌ Exception used for normal flow control (slow and unclear)
try:
    user = users[name]
except KeyError:
    user = create_default_user(name)

# ✅ Explicit check
user = users.get(name) or create_default_user(name)
```

```go
// ❌ Go: panic used for flow control
func getUser(id int) User {
    if id <= 0 {
        panic("invalid id")
    }
}

// ✅ Go: return an error
func getUser(id int) (User, error) {
    if id <= 0 {
        return User{}, fmt.Errorf("invalid user id: %d", id)
    }
}
```

### Anti-Pattern 5: Ignoring Return Values

```csharp
// ❌ Ignores the returned bool/Result
dict.TryGetValue("key", out var value);
// value may be the default, but the code continues as if the call succeeded

// ✅ Check the return value
if (!dict.TryGetValue("key", out var value))
{
    throw new KeyNotFoundException("key not found");
}
```

---

## Error Hierarchy Design

### Three-Layer Error Architecture

```
┌─────────────────────────────────────────────────┐
│ Application Errors (application level)          │
│   - AppError / ServiceError                     │
│   - Global handler sends user-friendly response │
├─────────────────────────────────────────────────┤
│ Module Errors (module level)                    │
│   - PaymentError, AuthError, ValidationError    │
│   - Each business module defines its own errors │
├─────────────────────────────────────────────────┤
│ Infrastructure Errors (infrastructure level)    │
│   - IOError, NetworkError, DatabaseError        │
│   - Low-level errors from OS, network, database │
└─────────────────────────────────────────────────┘
```

### Design Rules

1. **Module-level errors inherit from the application-level base class**, enabling a global catch
2. **Infrastructure errors are converted to module-level errors at module boundaries**, not exposed to upper layers
3. **Each error type carries enough context** for debugging (ID, timestamp, operation name)

### Example Hierarchy (Python)

```python
class AppError(Exception):
    """Base application exception"""
    pass

class PaymentError(AppError):
    """Payment module error"""
    def __init__(self, order_id: str, reason: str):
        self.order_id = order_id
        super().__init__(f"payment failed for order {order_id}: {reason}")

class PaymentGatewayTimeout(PaymentError):
    """Payment gateway timeout"""
    def __init__(self, order_id: str, gateway: str, timeout_ms: int):
        self.gateway = gateway
        self.timeout_ms = timeout_ms
        super().__init__(order_id, f"gateway {gateway} timed out after {timeout_ms}ms")
```

### Example Hierarchy (Java)

```java
public class AppException extends RuntimeException {
    private final String errorCode;
    public AppException(String errorCode, String message, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
    }
}

public class OrderNotFoundException extends AppException {
    public OrderNotFoundException(Long orderId) {
        super("ORDER_NOT_FOUND", "Order " + orderId + " not found", null);
    }
}
```

---

## Logging Best Practices

### Choosing a Log Level

| Level | When to use | Example |
|------|---------|------|
| **ERROR** | Failure requiring human intervention | Payment failed, data inconsistency |
| **WARN** | Anomaly that recovers automatically | Retry succeeded, graceful degradation |
| **INFO** | Normal business event | Order created, user logged in |
| **DEBUG** | Debugging information | Function arguments, intermediate state |

### Log Format

```
// ❌ No structured information
log.error("failed to process")

// ✅ Structured information + context
log.error("payment_failed", {
    "order_id": "12345",
    "gateway": "stripe",
    "error_code": "card_declined",
    "amount": 99.99,
    "duration_ms": 2340
})
```

### Log Security

- **Do not log sensitive information**: password, token, PII, full credit card number
- **Mask sensitive data**: `email: a***@example.com`
- **Log injection protection**: escape user input to prevent forged log lines

---

## Cross-Language Code Examples

### Python

```python
# ✅ Specific exception + context + exception chain
try:
    response = http_client.post(url, data=payload)
    response.raise_for_status()
except requests.ConnectionError as e:
    raise PaymentGatewayError(f"cannot reach {gateway_name}") from e
except requests.HTTPError as e:
    if response.status_code == 429:
        raise RateLimitError(f"rate limited by {gateway_name}") from e
    raise PaymentGatewayError(f"HTTP {response.status_code} from {gateway_name}") from e
```

### Java

```java
// ✅ Specific exception + context + cause chain
try {
    var response = httpClient.send(request, BodyHandlers.ofString());
    if (response.statusCode() == 404) {
        throw new OrderNotFoundException(orderId);
    }
} catch (IOException e) {
    throw new PaymentGatewayException(
        "gateway unreachable: " + gatewayUrl, e);
}
```

### Go

```go
// ✅ Error wrapping + context + %w preserves the chain
result, err := client.Do(req)
if err != nil {
    return fmt.Errorf("payment gateway %s request failed: %w", gatewayName, err)
}
defer result.Body.Close()

if result.StatusCode == http.StatusNotFound {
    return fmt.Errorf("order %d not found: %w", orderID, ErrNotFound)
}
```

### Rust

```rust
// ✅ thiserror defines the error type + context
#[derive(Debug, thiserror::Error)]
enum PaymentError {
    #[error("gateway {gateway} unreachable")]
    GatewayUnreachable {
        gateway: String,
        #[source]
        source: reqwest::Error,
    },
    #[error("order {order_id} not found")]
    OrderNotFound { order_id: u64 },
}

async fn process_payment(gateway: &str, order_id: u64) -> Result<(), PaymentError> {
    let response = client.post(url)
        .send()
        .await
        .map_err(|e| PaymentError::GatewayUnreachable {
            gateway: gateway.into(),
            source: e,
        })?;
    Ok(())
}
```

### C#

```csharp
// ✅ Specific exception + context
try
{
    var response = await httpClient.PostAsync(url, content);
    response.EnsureSuccessStatusCode();
}
catch (HttpRequestException ex) when (ex.StatusCode == HttpStatusCode.NotFound)
{
    throw new OrderNotFoundException(orderId, ex);
}
catch (HttpRequestException ex)
{
    throw new PaymentGatewayException($"gateway unreachable: {url}", ex);
}
```

### Swift

```swift
// ✅ Error enum + context
enum PaymentError: Error {
    case gatewayUnreachable(name: String, underlying: Error)
    case orderNotFound(id: Int)
    case declined(reason: String)
}

func processPayment(orderId: Int) throws -> Receipt {
    guard orderId > 0 else {
        throw PaymentError.orderNotFound(id: orderId)
    }
    do {
        let response = try networkClient.post(url, body: payload)
        return try Receipt(from: response)
    } catch let error as NetworkError {
        throw PaymentError.gatewayUnreachable(name: gateway, underlying: error)
    }
}
```

### TypeScript

```typescript
// ✅ Custom error class + context
class PaymentError extends Error {
    constructor(
        message: string,
        public readonly orderId: string,
        public readonly gateway: string,
        public readonly cause?: Error,
    ) {
        super(message);
        this.name = 'PaymentError';
    }
}

async function processPayment(orderId: string): Promise<Receipt> {
    try {
        const response = await fetch(url, { method: 'POST', body: payload });
        if (!response.ok) {
            throw new PaymentError(
                `gateway returned ${response.status}`,
                orderId,
                gatewayName,
            );
        }
        return await response.json();
    } catch (err) {
        if (err instanceof TypeError) {
            throw new PaymentError('gateway unreachable', orderId, gatewayName, err);
        }
        throw err;
    }
}
```

---

## Review Checklist

### Core Checks
- [ ] No empty catch blocks or silently ignored errors
- [ ] Error messages include the operation description and key parameters
- [ ] Specific error types are used (not generic Error/Exception)
- [ ] Exception chain is preserved (from / cause / %w)
- [ ] Preconditions are validated before the operation starts (fail fast)

### Architecture Checks
- [ ] A clear error hierarchy is defined (application/module/infrastructure)
- [ ] A global exception handler catches unhandled errors
- [ ] API boundary converts internal errors to appropriate HTTP status codes

### Logging Checks
- [ ] Error logs include structured context
- [ ] No sensitive information is logged (password, token, PII)
- [ ] Log levels are used correctly (ERROR vs WARN vs INFO)

### Language-Specific
- [ ] Go: error is not ignored, wrapped with `%w`
- [ ] Python: catch specific exceptions, use `from` to preserve the chain
- [ ] Java: exceptions have a cause, use specific types
- [ ] Rust: `?` propagation, custom Error types
- [ ] C#: when filters, specific exception types
- [ ] Swift: do-catch, Result for deferred handling
