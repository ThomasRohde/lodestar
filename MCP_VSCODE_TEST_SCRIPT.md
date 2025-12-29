# VS Code Copilot MCP Testing Script
## Task: MCP-094 - Test MCP server with real host

**IMPORTANT:** This script tests the **MCP server integration** only. All commands must use MCP tools, NOT the lodestar CLI.

---

## Pre-Test Setup

### 1. Configure VS Code Settings

Add to your VS Code settings (User or Workspace):

**File:** `.vscode/settings.json` (workspace) or User Settings JSON

```json
{
  "github.copilot.chat.mcp.servers": {
    "lodestar": {
      "command": "uv",
      "args": ["run", "lodestar", "mcp", "serve", "--repo", "C:\\Users\\thoma\\Projects\\lodestar"],
      "env": {}
    }
  }
}
```

### 2. Restart VS Code

Completely restart VS Code to initialize the MCP server connection.

### 3. Test Tasks Created

The following safe test tasks have been created for you:

- **MCP-TEST-1**: MCP Copilot Test Task 1
- **MCP-TEST-2**: MCP Copilot Test Task 2
- **MCP-TEST-3**: MCP Copilot Test Task 3

All are in "ready" status and safe to test with.

---

## Test Script for Copilot

Copy and paste these prompts **ONE AT A TIME** into VS Code Copilot Chat.

### Test 1: Verify MCP Connection

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

Use the lodestar_agent_list MCP tool to show me all registered agents.
```

**Expected:** Should return a list of agents via MCP tool call.

**Result:** [ ] PASS / [ ] FAIL

**Notes:**


---

### Test 2: Agent Registration

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

Use the lodestar_agent_join MCP tool to register me as a new agent with:
- role: "copilot-tester"
- capabilities: ["testing", "mcp"]

Save the returned agent_id for later use.
```

**Expected:** Returns a new agent ID.

**Result:** [ ] PASS / [ ] FAIL

**Agent ID:** _______________

---

### Test 3: List Available Tasks

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

Use the lodestar_task_list MCP tool to show all tasks with status="ready".
Filter to only show tasks with label="test".
```

**Expected:** Should show MCP-TEST-1, MCP-TEST-2, and MCP-TEST-3 (and possibly others).

**Result:** [ ] PASS / [ ] FAIL

**Notes:**


---

### Test 4: Find Next Claimable Task

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

Use the lodestar_task_next MCP tool to find the next claimable task.
```

**Expected:** Should return MCP-TEST-1 or another claimable task.

**Result:** [ ] PASS / [ ] FAIL

**Task ID returned:** _______________

---

### Test 5: Claim a Test Task

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

Use the lodestar_task_claim MCP tool to claim task "MCP-TEST-1" with agent_id "<YOUR_AGENT_ID_FROM_TEST2>".
```

**Expected:** Should successfully claim the task and return lease information.

**Result:** [ ] PASS / [ ] FAIL

**Lease ID:** _______________

---

### Test 6: Get Task Context

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

Use the lodestar_task_context MCP tool to get full context for task "MCP-TEST-1".
```

**Expected:** Should return task details with PRD context.

**Result:** [ ] PASS / [ ] FAIL

**Notes:**


---

### Test 7: Renew Lease

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

Use the lodestar_task_renew MCP tool to renew the lease for task "MCP-TEST-1".
```

**Expected:** Should extend the lease expiration time.

**Result:** [ ] PASS / [ ] FAIL

---

### Test 8: Mark Task as Done

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

Use the lodestar_task_done MCP tool to mark task "MCP-TEST-1" as done with agent_id "<YOUR_AGENT_ID>".
```

**Expected:** Should change task status to "done".

**Result:** [ ] PASS / [ ] FAIL

---

### Test 9: Verify Task

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

Use the lodestar_task_verify MCP tool to verify task "MCP-TEST-1" with agent_id "<YOUR_AGENT_ID>".
```

**Expected:** Should change task status to "verified".

**Result:** [ ] PASS / [ ] FAIL

---

### Test 10: Test Prompts

**Prompt:**
```
IMPORTANT: Use only MCP prompts, NOT the lodestar CLI command.

Show me the available MCP prompts from the lodestar server. Then invoke the "lodestar_agent_workflow" prompt.
```

**Expected:** Should list prompts and display the workflow guide.

**Result:** [ ] PASS / [ ] FAIL

**Prompts found:** _______________

---

## Two-Client Coordination Test

### Setup
1. Open **two separate VS Code windows** with the same repository
2. Both windows should have the MCP server configured

### Window 1 - First Client

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

1. Use lodestar_agent_join to register as agent with role "client-1"
2. Use lodestar_task_claim to claim task "MCP-TEST-2"
3. Show me the claim details
```

**Result:** [ ] PASS / [ ] FAIL

**Agent ID:** _______________

---

### Window 2 - Second Client

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

1. Use lodestar_agent_join to register as agent with role "client-2"
2. Use lodestar_task_list to show all tasks
3. Check if MCP-TEST-2 shows as claimed by another agent
```

**Expected:** MCP-TEST-2 should show as claimed by client-1.

**Result:** [ ] PASS / [ ] FAIL

**Notes:**


---

### Window 2 - Try to Claim Same Task

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

Try to use lodestar_task_claim to claim task "MCP-TEST-2" (which is already claimed).
```

**Expected:** Should fail with "already claimed" error.

**Result:** [ ] PASS / [ ] FAIL

---

## State Transition Testing

### Test Complete Lifecycle

**Prompt (in one window):**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

Execute this complete workflow using MCP tools:

1. Join as agent (role: "lifecycle-tester")
2. List tasks to find an unclaimed test task
3. Claim the task
4. Get task context
5. Mark task as done
6. Verify task
7. List tasks again to confirm status is "verified"

Show me each step's output.
```

**Expected:** Full workflow should complete successfully.

**Result:** [ ] PASS / [ ] FAIL

---

## Error Handling Tests

### Test Invalid Task ID

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

Use lodestar_task_get to try to get task "INVALID-999".
```

**Expected:** Should return appropriate error message.

**Result:** [ ] PASS / [ ] FAIL

---

### Test Claim Without Agent

**Prompt:**
```
IMPORTANT: Use only MCP tools, NOT the lodestar CLI command.

Try to use lodestar_task_claim to claim a task with an invalid agent_id "FAKE-AGENT".
```

**Expected:** Should fail with agent not found error.

**Result:** [ ] PASS / [ ] FAIL

---

## Performance Observations

1. **Connection startup time:** _______________
2. **Average tool response time:** _______________
3. **Any lag or delays?** _______________
4. **Memory usage (check Task Manager):** _______________

---

## Issues Found

Document any issues, errors, or unexpected behavior:

1.

2.

3.

---

## Improvements Needed

List any UX improvements or missing features:

1.

2.

3.

---

## Cleanup

After testing, clean up the test tasks:

```bash
uv run lodestar task delete MCP-TEST-1 --cascade
uv run lodestar task delete MCP-TEST-2 --cascade
uv run lodestar task delete MCP-TEST-3 --cascade
```

---

## Final Checklist

- [ ] VS Code successfully connected to MCP server
- [ ] All Lodestar tools are accessible via Copilot
- [ ] Agent registration works (join)
- [ ] Task listing works (list, next)
- [ ] Task claiming works (claim)
- [ ] Task context retrieval works (get, context)
- [ ] Lease renewal works (renew)
- [ ] Task completion works (done, verify)
- [ ] Two clients can coordinate via same repo
- [ ] Task state transitions work correctly
- [ ] Prompts are accessible and work
- [ ] Error handling is appropriate
- [ ] No critical bugs found

---

## Completion

Once all tests are complete:

```bash
uv run lodestar task done MCP-094 --agent A016709FC
uv run lodestar task verify MCP-094 --agent A016709FC
```

---

**Test Date:** _______________
**Tested By:** _______________
**VS Code Version:** _______________
**Copilot Version:** _______________
**Overall Result:** [ ] PASS / [ ] FAIL
