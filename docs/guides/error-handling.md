# Error Handling Guide

This guide explains how to handle errors when using Lodestar's MCP server, including which errors are retriable and recommended recovery strategies.

## Error Classification

Lodestar errors fall into two categories:

1. **Retriable Errors**: Transient failures that may succeed on retry (e.g., file system locks, network timeouts)
2. **Non-Retriable Errors**: Permanent failures that require user intervention (e.g., invalid input, missing files)

## Common Error Types

### Spec Errors

All spec-related errors inherit from `SpecError` and include metadata about whether they're retriable.

#### SpecNotFoundError

**Category**: Non-Retriable

**Cause**: The `.lodestar/spec.yaml` file doesn't exist.

**Example**:
```json
{
  "error": "Spec not found: C:\\Users\\user\\project\\.lodestar\\spec.yaml",
  "retriable": false,
  "suggested_action": "Run 'lodestar init' to initialize the repository"
}
```

**How to Handle**:
```python
# Don't retry - the repository needs initialization
if "Spec not found" in error_message:
    print("Repository not initialized. Run 'lodestar init' first.")
    return
```

---

#### SpecValidationError

**Category**: Non-Retriable

**Cause**: The spec file contains invalid YAML or doesn't match the schema.

**Example**:
```json
{
  "error": "Spec validation failed: Invalid YAML: ...",
  "retriable": false,
  "suggested_action": "Fix the spec file or restore from backup"
}
```

**How to Handle**:
```python
# Don't retry - the spec file is corrupt or invalid
if "Spec validation failed" in error_message:
    print("Spec file is invalid. Check .lodestar/spec.yaml for syntax errors.")
    return
```

---

#### SpecLockError

**Category**: Retriable

**Cause**: Another process has acquired the file lock on `spec.lock`.

**Example**:
```json
{
  "error": "Failed to acquire spec lock: Timeout",
  "retriable": true,
  "suggested_action": "Retry immediately (lock timeout was 5.0s)",
  "timeout": 5.0
}
```

**How to Handle**:
```python
# Retry with exponential backoff
max_attempts = 3
for attempt in range(max_attempts):
    try:
        result = lodestar_task_claim(task_id, agent_id)
        break  # Success!
    except SpecLockError as e:
        if attempt < max_attempts - 1:
            delay = 0.1 * (2 ** attempt)  # 100ms, 200ms, 400ms
            time.sleep(delay)
        else:
            raise  # Give up after max attempts
```

---

#### SpecFileAccessError

**Category**: Retriable

**Cause**: Windows file system lock during atomic rename operation (most common) or other temporary file access issue.

**Example**:
```json
{
  "error": "[WinError 5] Access is denied: 'spec.tmp' -> 'spec.yaml'",
  "retriable": true,
  "suggested_action": "Retry immediately (transient Windows file lock during atomic rename)",
  "operation": "atomic rename"
}
```

**Frequency**: ~40% of operations on Windows (based on testing)

**How to Handle**:
```python
# Immediate retry usually succeeds on Windows
try:
    result = lodestar_task_verify(task_id, agent_id)
except SpecFileAccessError:
    # Wait briefly and retry once
    time.sleep(0.05)  # 50ms
    result = lodestar_task_verify(task_id, agent_id)
```

**Note**: Lodestar includes internal retry logic for these errors, but external retries may still be needed for some edge cases.

---

### Validation Errors

Input validation errors are raised before any file operations occur.

#### ValidationError

**Category**: Non-Retriable

**Cause**: Invalid input parameters (e.g., message too long, invalid TTL, missing required field).

**Examples**:

```json
{
  "error": "message exceeds maximum length of 16384 bytes",
  "field": "message"
}
```

```json
{
  "error": "agent_id is required for this operation",
  "field": "agent_id"
}
```

```json
{
  "error": "task_id cannot be empty",
  "field": "task_id"
}
```

**How to Handle**:
```python
# Don't retry - fix the input
try:
    result = lodestar_message_send(from_agent_id, task_id, message_body)
except ValidationError as e:
    if "exceeds maximum" in str(e):
        # Truncate message and resend
        message_body = message_body[:16000]  # Leave room for encoding
        result = lodestar_message_send(from_agent_id, task_id, message_body)
    else:
        raise  # Other validation errors need different fixes
```

---

### Task State Errors

#### TaskNotClaimableError

**Category**: Non-Retriable (but state may change)

**Cause**: Task status is not `ready`, or dependencies are not satisfied.

**Example**:
```json
{
  "error": "Task F002 is not claimable (status: done, unmet dependencies: [])"
}
```

**How to Handle**:
```python
# Check task state before claiming
task = lodestar_task_get(task_id)
if not task["claimable"]:
    print(f"Task {task_id} is not claimable: {task['status']}")
    # Find another task
    candidates = lodestar_task_next(agent_id, limit=5)
    if candidates["candidates"]:
        next_task = candidates["candidates"][0]
        lodestar_task_claim(next_task["id"], agent_id)
```

---

#### LeaseConflictError

**Category**: Non-Retriable (wait for lease expiry)

**Cause**: Task is already claimed by another agent.

**Example**:
```json
{
  "error": "Task F002 is already claimed by agent A5678EFGH (lease expires at 2025-01-15T11:00:00Z)"
}
```

**How to Handle**:
```python
# Wait for lease expiry or find another task
try:
    result = lodestar_task_claim(task_id, agent_id)
except LeaseConflictError as e:
    # Parse expiry time from error message
    expires_at = parse_expiry_time(str(e))
    
    if expires_at - now() < timedelta(minutes=2):
        # Lease expires soon, wait for it
        wait_until(expires_at)
        result = lodestar_task_claim(task_id, agent_id)
    else:
        # Lease is long-lived, find another task
        candidates = lodestar_task_next(agent_id, limit=5)
```

---

### PRD Context Errors

#### AnchorNotFoundError

**Category**: Non-Retriable

**Cause**: Referenced PRD anchor (e.g., `## Section Name`) doesn't exist in the PRD file.

**Example**:
```json
{
  "error": "Anchor '## Authentication' not found in C:\\project\\PRD.md"
}
```

**How to Handle**:
```python
# PRD has changed - context may be stale
try:
    context = lodestar_task_context(task_id)
except ValueError as e:
    if "Anchor" in str(e) and "not found" in str(e):
        print("Warning: PRD structure changed. Task context may be outdated.")
        # Continue with task description only
        task = lodestar_task_get(task_id)
        context = task["description"]
```

---

## Retry Strategies

### Immediate Retry (Recommended for SpecFileAccessError)

For Windows file system locks that clear almost immediately:

```python
def retry_immediate(func, max_attempts=2):
    """Retry once with minimal delay."""
    for attempt in range(max_attempts):
        try:
            return func()
        except SpecFileAccessError:
            if attempt < max_attempts - 1:
                time.sleep(0.05)  # 50ms
            else:
                raise
```

**Use for**: `task.done`, `task.verify`, `task.claim`

---

### Exponential Backoff (Recommended for SpecLockError)

For lock contention with multiple agents:

```python
def retry_exponential(func, max_attempts=3, base_delay=0.1):
    """Retry with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            return func()
        except (SpecLockError, SpecFileAccessError) as e:
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise
```

**Use for**: Any operation during high concurrency

---

### Conditional Retry

Only retry specific error types:

```python
def is_retriable_error(error):
    """Check if an error should be retried."""
    if hasattr(error, 'retriable'):
        return error.retriable
    
    # Check error message for known retriable patterns
    error_str = str(error)
    retriable_patterns = [
        "Access is denied",
        "WinError 5",
        "WinError 32",
        "Failed to acquire spec lock",
    ]
    return any(pattern in error_str for pattern in retriable_patterns)

def smart_retry(func, max_attempts=3):
    """Only retry retriable errors."""
    last_error = None
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            last_error = e
            if not is_retriable_error(e):
                raise  # Don't retry non-retriable errors
            if attempt < max_attempts - 1:
                time.sleep(0.1 * (2 ** attempt))
    raise last_error
```

---

## Complete Example

Here's a production-ready error handling wrapper for MCP tools:

```python
import time
from typing import Callable, TypeVar, Any

T = TypeVar('T')

class LodestarErrorHandler:
    """Production-ready error handling for Lodestar MCP tools."""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
    
    def call(self, func: Callable[[], T], operation_name: str) -> T:
        """Call a Lodestar MCP tool with automatic retry logic.
        
        Args:
            func: The MCP tool call (as a lambda with no args)
            operation_name: Human-readable operation name for logging
            
        Returns:
            The result from the MCP tool
            
        Raises:
            The last error if all retries fail
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return func()
                
            except SpecFileAccessError as e:
                # Windows file lock - retry immediately
                last_error = e
                if attempt < self.max_retries - 1:
                    print(f"Retry {operation_name} (Windows file lock)")
                    time.sleep(0.05)  # 50ms
                    
            except SpecLockError as e:
                # Lock contention - exponential backoff
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = 0.1 * (2 ** attempt)
                    print(f"Retry {operation_name} after {delay}s (lock held)")
                    time.sleep(delay)
                    
            except (SpecNotFoundError, SpecValidationError, ValidationError):
                # Non-retriable - fail fast
                raise
                
            except Exception as e:
                # Unknown error - don't retry
                print(f"Unknown error in {operation_name}: {e}")
                raise
        
        # All retries exhausted
        print(f"Failed {operation_name} after {self.max_retries} attempts")
        raise last_error

# Usage example
handler = LodestarErrorHandler(max_retries=3)

# Claim a task with automatic retries
result = handler.call(
    lambda: lodestar_task_claim("F002", "A1234ABCD"),
    operation_name="task.claim"
)

# Mark done with automatic retries
result = handler.call(
    lambda: lodestar_task_done("F002", "A1234ABCD"),
    operation_name="task.done"
)

# Verify with automatic retries
result = handler.call(
    lambda: lodestar_task_verify("F002", "A1234ABCD"),
    operation_name="task.verify"
)
```

---

## Testing Your Error Handling

### Simulate Windows File Locks

Test your retry logic on Windows by running concurrent operations:

```python
import threading

def concurrent_verify():
    """Verify multiple tasks simultaneously to trigger file locks."""
    threads = []
    for task_id in ["F001", "F002", "F003"]:
        t = threading.Thread(
            target=lambda tid: handler.call(
                lambda: lodestar_task_verify(tid, agent_id),
                f"verify {tid}"
            ),
            args=(task_id,)
        )
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
```

### Simulate Lock Contention

Test lock handling with multiple agents:

```python
def multi_agent_claim():
    """Multiple agents try to claim the same task."""
    agents = ["A111", "A222", "A333"]
    task_id = "F001"
    
    for agent_id in agents:
        try:
            result = handler.call(
                lambda: lodestar_task_claim(task_id, agent_id),
                f"agent {agent_id} claim"
            )
            print(f"{agent_id} won the claim")
            break
        except LeaseConflictError:
            print(f"{agent_id} lost - already claimed")
            # Find another task
            candidates = lodestar_task_next(agent_id, limit=1)
            if candidates["candidates"]:
                task_id = candidates["candidates"][0]["id"]
```

---

## Best Practices

### 1. Always Check `retriable` Flag

When possible, use the error metadata:

```python
try:
    result = lodestar_task_claim(task_id, agent_id)
except SpecError as e:
    if e.retriable:
        # Retry with backoff
        time.sleep(0.1)
        result = lodestar_task_claim(task_id, agent_id)
    else:
        # Don't retry - handle gracefully
        print(f"Permanent error: {e}")
        print(f"Suggested action: {e.suggested_action}")
```

### 2. Use task.complete for Atomic Operations

Prefer `task.complete` over separate `task.done` + `task.verify` to reduce error surface:

```python
# Better: Atomic operation
result = handler.call(
    lambda: lodestar_task_complete(task_id, agent_id),
    operation_name="task.complete"
)

# Avoid: Two operations = two potential failure points
# lodestar_task_done(task_id, agent_id)     # Might fail here
# lodestar_task_verify(task_id, agent_id)   # Or here
```

### 3. Log Retry Attempts

Help with debugging by logging retries:

```python
import logging

logger = logging.getLogger("lodestar.mcp")

def logged_retry(func, operation):
    for attempt in range(3):
        try:
            return func()
        except SpecFileAccessError as e:
            logger.warning(
                f"Retry {operation} (attempt {attempt + 1}/3): {e}"
            )
            if attempt < 2:
                time.sleep(0.05)
            else:
                raise
```

### 4. Set Reasonable Timeouts

Don't retry forever:

```python
from datetime import datetime, timedelta

def retry_with_timeout(func, timeout_seconds=30):
    """Retry until success or timeout."""
    deadline = datetime.now() + timedelta(seconds=timeout_seconds)
    
    while datetime.now() < deadline:
        try:
            return func()
        except SpecFileAccessError:
            time.sleep(0.1)
    
    raise TimeoutError(f"Operation timed out after {timeout_seconds}s")
```

### 5. Handle Graceful Degradation

When context is unavailable, fall back to basics:

```python
try:
    # Try to get full PRD context
    context = lodestar_task_context(task_id, max_chars=2000)
    full_context = context["content"]
except Exception as e:
    # Fall back to task description only
    logger.warning(f"Could not load PRD context: {e}")
    task = lodestar_task_get(task_id)
    full_context = task["description"]
```

---

## Platform-Specific Notes

### Windows

- **File system locks are common**: Expect `SpecFileAccessError` on 20-40% of operations
- **Immediate retry usually works**: 50ms delay is sufficient
- **Antivirus can cause locks**: Windows Defender may briefly lock files during scans

### Linux/macOS

- **Locks are rare**: `SpecLockError` only occurs during true contention
- **Faster operations**: File system operations are typically 2-3x faster
- **NFS can cause issues**: Networked file systems may have stale lock files

---

## Migration from v0.1.x

In current Lodestar releases, internal retry logic handles most Windows file system issues. If you have existing retry logic:

**Before** (v0.1.x - external retry required):
```python
for _ in range(3):
    try:
        lodestar_task_verify(task_id, agent_id)
        break
    except:
        time.sleep(0.1)
```

**After** (internal retry, but external still helps):
```python
try:
    lodestar_task_verify(task_id, agent_id)
except SpecFileAccessError:
    # Rare, but can still happen in edge cases
    time.sleep(0.05)
    lodestar_task_verify(task_id, agent_id)
```

---

## See Also

- [Agent Workflow Guide](agent-workflow.md) - Complete agent coordination workflow
- [MCP Server Documentation](../mcp.md) - MCP tools reference
- [Lease Mechanics](../concepts/lease-mechanics.md) - Understanding task leases
