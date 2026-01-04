# MCP Feature Test - Coding Agent Instructions

**Objective**: Thoroughly test Lodestar's MCP (Model Context Protocol) features, including recent file locking improvements in loader.py, while creating and managing tasks using both MCP tools and CLI commands.

## Test Scope

This test validates:
1. MCP tools for task/agent/message operations
2. Concurrent access and file locking reliability
3. CLI task creation and management
4. Integration between MCP and CLI workflows
5. Resource notifications and progress tracking

## Prerequisites

Before starting:
- Ensure you have access to the Lodestar MCP server
- Verify CLI is available: `uv run lodestar --help`
- Check repository status: `uv run lodestar status --json`

## Test Workflow

### Phase 1: Agent Registration (MCP + CLI)

**Test 1A - MCP Agent Join**
```
Use the MCP tool: lodestar.agent.join
- Register with name "MCP-Test-Agent-1"
- Save the returned agent_id for subsequent tests
- Verify the response includes agentId, joinedAt, and ttl defaults
```

**Test 1B - CLI Agent Join**
```bash
# Create a second agent via CLI
uv run lodestar agent join --name "CLI-Test-Agent-1" --json
```

**Validation**: 
- List all agents using `lodestar.agent.list` MCP tool
- Verify both agents appear with correct names and status
- Check that agent IDs are unique and properly formatted

### Phase 2: Task Creation (CLI Focus)

Create a set of interconnected tasks to test dependency handling:

**Test 2A - Create Base Tasks**
```bash
# Task 1: Foundation task (no dependencies)
uv run lodestar task create \
  --id "TEST-001" \
  --title "Setup test database schema" \
  --description "WHAT: Create initial database tables for user management.
WHERE: src/database/schema.py
WHY: Foundation for authentication system.
ACCEPT: 1) Tables created 2) Migrations work 3) Tests pass
CONTEXT: Use SQLAlchemy models, follow patterns in existing schema files" \
  --priority 1 \
  --label test

# Task 2: Depends on TEST-001
uv run lodestar task create \
  --id "TEST-002" \
  --title "Implement user authentication" \
  --description "WHAT: Add login/logout endpoints with JWT tokens.
WHERE: src/auth/, tests/test_auth.py
WHY: Enable user sessions.
ACCEPT: 1) POST /login works 2) Token validation 3) 95% test coverage
CONTEXT: Database schema ready from TEST-001" \
  --priority 2 \
  --label test \
  --depends-on "TEST-001"

# Task 3: Depends on TEST-002
uv run lodestar task create \
  --id "TEST-003" \
  --title "Add user profile management" \
  --description "WHAT: CRUD operations for user profiles.
WHERE: src/profiles/, tests/test_profiles.py
WHY: Allow users to manage their data.
ACCEPT: 1) All CRUD ops work 2) Auth required 3) Tests pass
CONTEXT: Requires auth from TEST-002, uses schema from TEST-001" \
  --priority 3 \
  --label test \
  --depends-on "TEST-002"

# Task 4: Parallel to TEST-002 (also depends on TEST-001)
uv run lodestar task create \
  --id "TEST-004" \
  --title "Add database indexing" \
  --description "WHAT: Create indexes for common queries.
WHERE: src/database/indexes.py
WHY: Performance optimization.
ACCEPT: 1) Indexes created 2) Query time < 100ms 3) Migration tested
CONTEXT: Works with schema from TEST-001, independent of auth" \
  --priority 2 \
  --label test \
  --depends-on "TEST-001"
```

**Validation**:
- Use `lodestar.task.list` MCP tool to verify all tasks created
- Use `lodestar.task.get` MCP tool to inspect each task's dependencies
- Verify dependency graph is correct using `uv run lodestar task graph`

### Phase 3: Concurrent MCP Operations (File Locking Test)

**Test 3A - Rapid Task Claims**
```
Simulate concurrent claims by:
1. Use lodestar.task.next to find claimable tasks
2. Attempt to claim TEST-001 with your MCP agent (use saved agent_id)
3. IMMEDIATELY attempt to claim TEST-001 again with the same agent
4. Verify the second claim fails with appropriate error
5. Verify lease is held by first claim
```

**Test 3B - Concurrent Task Updates**
```
Test file locking improvements:
1. Mark TEST-001 as done using lodestar.task.done
2. Immediately try to claim TEST-001 again (should fail - task is done)
3. Verify task status updated correctly
4. Check that TEST-002 and TEST-004 became claimable
```

**Test 3C - Message Sending During Operations**
```
While tasks are in various states:
1. Send message to task thread using lodestar.message.send (from_agent_id, task_id, body)
2. List messages in task thread using lodestar.message.list (task_id)
3. Mark messages as read using lodestar.message.ack (task_id, agent_id)
```

!!! note "Task-Only Messaging"
    Lodestar uses task-targeted messaging only. All messages are sent to task threads where all agents working on the task can see them. There is no agent-to-agent direct messaging.

### Phase 4: Task Lifecycle (MCP Tools)

**Important Note on Dependencies:**
Dependencies must be **verified** (not just done) before a dependent task becomes claimable.
The workflow is: claim → done → verify. Only after verify do dependent tasks unblock.

**Test 4A - Complete Workflow for TEST-001**
```
1. Claim TEST-001 using lodestar.task.claim
2. Get PRD context using lodestar.task.context
3. "Work" on the task (wait 5 seconds to simulate work)
4. Renew lease if needed (test TTL)
5. Mark as done using lodestar.task.done
6. Verify using lodestar.task.verify
7. Check that dependent tasks (TEST-002, TEST-004) are now claimable
```

**Test 4B - Parallel Task Execution**
```
Now that TEST-002 and TEST-004 are claimable:
1. Claim TEST-002 with your MCP agent
2. Have CLI agent claim TEST-004 using: 
   uv run lodestar task claim TEST-004 --agent <cli-agent-id> --json
3. Complete both tasks concurrently:
   - Mark TEST-002 done via MCP
   - Mark TEST-004 done via CLI
4. Verify both via MCP tools
5. Check that TEST-003 is now claimable
```

### Phase 5: Event Stream and Messages

**Test 5A - Event Pull**
```
1. Use lodestar.events.pull with since_cursor=0 to get all events
2. Verify you see: agent joins, task claims, task completions
3. Save the nextCursor value
4. Perform a new operation (e.g., send a message)
5. Pull events again with previous nextCursor
6. Verify you only see new events
```

**Test 5B - Message Threading**
```
1. Send message to TEST-003 task thread: "Ready to start TEST-003"
2. Send another message to same thread: "Clarifying requirements"
3. List messages with lodestar.message.list (unread_only=true)
4. Acknowledge one message using lodestar.message.ack
5. List again and verify only one message remains unread
```

### Phase 6: Error Handling and Edge Cases

**Test 6A - Invalid Operations**
```
Test error handling:
1. Try to claim a non-existent task (expect error)
2. Try to claim TEST-003 (should fail - unmet dependencies)
3. Try to verify a task that's not done (expect error)
4. Try to claim with invalid agent_id (expect error)
5. Try to release a lease you don't own (expect error)
```

**Test 6B - Lease Expiration**
```
1. Claim TEST-003 with very short TTL (60 seconds)
2. Wait for lease to expire (or manually advance time if possible)
3. Try to renew expired lease (should fail)
4. Verify another agent can now claim TEST-003
```

**Test 6C - Concurrent Write Conflicts**
```
Test file locking under load:
1. Create 5 new simple tasks (TEST-005 through TEST-009)
2. Try to claim all 5 rapidly in succession
3. Verify all claims either succeed or fail cleanly (no corruption)
4. Check spec.yaml integrity: uv run lodestar doctor
```

### Phase 7: Repository Status and Statistics

**Test 7A - Status Monitoring**
```
1. Use lodestar.repo.status MCP tool
2. Verify task counts match expected state
3. Check agent statistics are accurate
4. Verify suggested next actions are appropriate
```

**Test 7B - Task Filtering**
```
1. List tasks with status="ready" filter
2. List tasks with status="verified" filter
3. List tasks with label="test" filter
4. Verify pagination works with limit and cursor parameters
```

## Expected Outcomes

After completing all tests:

✅ **Task State**:
- TEST-001: verified
- TEST-002: verified  
- TEST-003: done or verified (if completed in Test 6B)
- TEST-004: verified
- TEST-005 to TEST-009: claimed or ready

✅ **Agent State**:
- 2 agents registered (1 MCP, 1 CLI)
- Both have heartbeats within last 5 minutes
- Message counts > 0 for both agents

✅ **Messages**:
- Task thread messages for TEST-001, TEST-003
- Direct messages between agents
- Some messages marked as read

✅ **Events**:
- Event stream contains complete audit trail
- All operations logged with correct timestamps
- nextCursor pagination works

✅ **System Health**:
- `uv run lodestar doctor` passes all checks
- No corrupted spec.yaml or runtime.sqlite
- No orphaned leases
- No file locking errors in any operation

## Validation Commands

Run these to verify final state:

```bash
# Overall status
uv run lodestar status --json

# Task summary
uv run lodestar task list --json

# Agent summary  
uv run lodestar agent list --json

# System health
uv run lodestar doctor --json

# Full snapshot
uv run lodestar export snapshot > test-results.json
```

## Reporting

After completing tests, report:

1. **Success Rate**: X/Y tests passed
2. **Performance**: Average response time for MCP calls
3. **File Locking**: Any contention or errors during concurrent ops
4. **Error Handling**: Were errors clear and actionable?
5. **Issues Found**: List any bugs, race conditions, or UX problems
6. **Recommendations**: Suggested improvements

## Notes for Testing Agent

- **Be thorough**: Don't skip tests even if previous ones passed
- **Check errors**: Failed operations should return clear error messages
- **Use --json**: Parse JSON output for programmatic validation
- **Time operations**: Note if any MCP calls are unusually slow
- **Check logs**: Look for warnings in console output
- **Test concurrency**: The file locking fixes are critical - really stress test them

## File Locking Specific Tests

Since loader.py was improved, specifically verify:

1. **Write Conflicts**: Multiple agents trying to update spec.yaml simultaneously
2. **Read During Write**: Listing tasks while another operation updates spec
3. **Atomic Operations**: Task creation/update is all-or-nothing (no partial writes)
4. **Lock Timeout**: Operations don't hang indefinitely if lock is held
5. **Lock Release**: Locks are always released, even after errors

Test these by:
- Running multiple `lodestar task create` commands rapidly in parallel
- Claiming/releasing/completing tasks in rapid succession via MCP
- Monitoring spec.yaml file integrity throughout

---

**Good luck! Focus on breaking things - that's how we find bugs. 🐛**
