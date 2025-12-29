# MCP Server

The Lodestar MCP (Model Context Protocol) server exposes Lodestar's multi-agent coordination capabilities through a standardized interface that MCP-compatible hosts (VS Code, Claude Desktop, and other IDEs) can integrate with directly.

This enables AI coding agents to coordinate tasks, claim work, and communicate—all without shell commands.

## What is MCP?

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/) is an open protocol that lets AI assistants integrate with external tools and data sources in a standardized way. Lodestar implements an MCP server that exposes:

- **Tools**: Operations like claiming tasks, sending messages, and marking work complete
- **Resources**: Read-only access to repository state (spec, status, tasks)
- **Events**: Real-time updates about task changes and messages (via pull API)

## Installation

The MCP server requires the optional `mcp` dependency group:

**Using uv (recommended):**

```bash
uv add 'lodestar-cli[mcp]'
```

**Using pip:**

```bash
pip install 'lodestar-cli[mcp]'
```

**Verify installation:**

```bash
lodestar mcp serve --help
```

## Running the MCP Server

### Basic Usage

The MCP server runs as a subprocess and communicates via stdio (JSON-RPC over standard input/output):

```bash
lodestar mcp serve
```

This will:

- Auto-discover the Lodestar repository (walks up from current directory)
- Start the server on stdio transport
- Log diagnostics to stderr
- Wait for MCP protocol messages on stdin

### Command Options

| Option | Description |
|--------|-------------|
| `--repo PATH` | Explicit repository path (default: auto-discover) |
| `--stdio` / `--no-stdio` | Use stdio transport (default: true, currently only option) |
| `--log-file PATH` | Write logs to file in addition to stderr |
| `--json-logs` | Use JSON format for logs |
| `--dev` | Enable development mode |

### Example: Explicit Repository

```bash
lodestar mcp serve --repo /path/to/my/lodestar/repo
```

### Example: File Logging

```bash
lodestar mcp serve --log-file mcp-server.log
```

Logs will be written to both `stderr` and `mcp-server.log`.

## Host Configuration

MCP hosts launch `lodestar mcp serve` as a subprocess. Here are example configurations for common hosts:

### VS Code

Add to your VS Code MCP configuration (typically in `.vscode/mcp.json` or user settings):

```json
{
  "mcpServers": {
    "lodestar": {
      "command": "lodestar",
      "args": ["mcp", "serve", "--repo", "${workspaceFolder}"],
      "env": {}
    }
  }
}
```

!!! note "UV users"
    If you installed Lodestar with `uv`, you may need to use `uv run lodestar` instead of `lodestar`:

    ```json
    {
      "command": "uv",
      "args": ["run", "lodestar", "mcp", "serve", "--repo", "${workspaceFolder}"]
    }
    ```

### Claude Desktop

Add to `claude_desktop_config.json` (location varies by platform):

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "lodestar": {
      "command": "lodestar",
      "args": ["mcp", "serve", "--repo", "/absolute/path/to/your/repo"],
      "env": {}
    }
  }
}
```

Replace `/absolute/path/to/your/repo` with the actual path to your Lodestar-initialized repository.

!!! warning "Use absolute paths"
    Claude Desktop launches servers from an unpredictable working directory. Always use `--repo` with an absolute path.

!!! note "Windows Path Format"
    On Windows, use either forward slashes or escaped backslashes in paths:
    
    **Forward slashes (recommended):**
    ```json
    "args": ["mcp", "serve", "--repo", "C:/Users/YourName/Projects/my-repo"]
    ```
    
    **Escaped backslashes:**
    ```json
    "args": ["mcp", "serve", "--repo", "C:\\Users\\YourName\\Projects\\my-repo"]
    ```
    
    For UV users on Windows:
    ```json
    {
      "command": "uv",
      "args": ["run", "lodestar", "mcp", "serve", "--repo", "C:/Users/YourName/Projects/my-repo"]
    }
    ```

### Other MCP Hosts

Any MCP-compatible host that supports stdio transport can connect to Lodestar. The server:

- Writes protocol messages to stdout
- Reads protocol messages from stdin
- Logs diagnostics to stderr

## MCP Tools Reference

Tools are organized into namespaced groups. All tools return both human-readable text summaries and structured `structuredContent` for parsing.

### Repository Tools

#### `lodestar.repo.status`

Get repository overview with task counts, agent statistics, and suggested next actions.

**Inputs:** None

**Returns:**

```json
{
  "repoRoot": "/path/to/repo",
  "specPath": "/path/to/repo/.lodestar/spec.yaml",
  "runtimePath": "/path/to/repo/.lodestar/runtime.sqlite",
  "project": {
    "name": "my-project",
    "defaultBranch": "main"
  },
  "counts": {
    "tasks": {
      "total": 42,
      "byStatus": {
        "ready": 5,
        "done": 10,
        "verified": 25,
        "deleted": 2
      },
      "claimable": 3
    },
    "agents": {
      "registered": 2,
      "activeLeases": 1
    },
    "messages": {
      "total": 8,
      "unread": 2
    }
  },
  "suggestedNextActions": [
    {"action": "task.next", "description": "Get next claimable task (3 available)"}
  ]
}
```

---

### Agent Tools

#### `lodestar.agent.join`

Register as an agent to begin claiming tasks.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | No | Display name for the agent |
| `client` | string | No | Host name/version (e.g., "vscode", "claude-desktop") |
| `model` | string | No | Model identifier (e.g., "claude-3.5-sonnet") |
| `capabilities` | object | No | Agent capabilities (reserved for future use) |

**Returns:**

```json
{
  "agentId": "A1234ABCD",
  "registeredAt": "2025-01-15T10:30:00Z",
  "suggestedNextActions": [
    {"action": "task.next", "description": "Get next claimable task"}
  ]
}
```

#### `lodestar.agent.heartbeat`

Update agent heartbeat timestamp to show the agent is still active.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_id` | string | Yes | Agent ID from `agent.join` |

**Returns:**

```json
{
  "agentId": "A1234ABCD",
  "heartbeatAt": "2025-01-15T10:35:00Z"
}
```

#### `lodestar.agent.leave`

Mark agent as offline gracefully.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_id` | string | Yes | Agent ID |
| `reason` | string | No | Reason for leaving (optional) |

**Returns:**

```json
{
  "agentId": "A1234ABCD",
  "leftAt": "2025-01-15T11:00:00Z",
  "reason": "Session ended"
}
```

---

### Task Tools

#### `lodestar.task.list`

List tasks with optional filtering and pagination.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | string | No | Filter by status (ready, done, verified, deleted, all) |
| `label` | string | No | Filter by label |
| `limit` | integer | No | Max results (default 50, max 200) |
| `cursor` | string | No | Pagination cursor (task ID to start after) |

**Returns:**

```json
{
  "items": [
    {
      "id": "F001",
      "title": "Implement user authentication",
      "status": "verified",
      "priority": 1,
      "labels": ["feature", "security"],
      "dependencies": [],
      "claimedByAgentId": null,
      "leaseExpiresAt": null,
      "updatedAt": "2025-01-15T09:00:00Z"
    }
  ],
  "total": 42,
  "meta": {
    "nextCursor": "F050",
    "filters": {
      "status": "ready",
      "label": null
    }
  }
}
```

#### `lodestar.task.get`

Get detailed information about a specific task.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | Task ID (e.g., "F001") |

**Returns:**

```json
{
  "id": "F001",
  "title": "Implement user authentication",
  "description": "Add email/password authentication...",
  "acceptanceCriteria": "- Users can register\n- Users can log in...",
  "status": "ready",
  "priority": 1,
  "labels": ["feature", "security"],
  "locks": ["src/auth/**"],
  "createdAt": "2025-01-10T10:00:00Z",
  "updatedAt": "2025-01-15T09:00:00Z",
  "dependencies": {
    "dependsOn": [],
    "dependents": ["F002", "F003"],
    "isClaimable": true
  },
  "prd": {
    "source": "PRD.md",
    "refs": [{"anchor": "## Authentication", "lines": [10, 25]}],
    "excerpt": "Frozen PRD excerpt...",
    "prdHash": "abc123..."
  },
  "runtime": {
    "claimed": false,
    "claimedBy": null
  },
  "warnings": []
}
```

#### `lodestar.task.next`

Get next claimable tasks sorted by priority.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_id` | string | No | Agent ID for personalization (reserved for future use) |
| `limit` | integer | No | Max results (default 5, max 20) |

**Returns:**

```json
{
  "candidates": [
    {
      "id": "F002",
      "title": "Add password reset",
      "status": "ready",
      "priority": 1,
      "labels": ["feature"],
      "dependencies": ["F001"]
    }
  ],
  "rationale": "Found 3 claimable task(s), showing top 5 by priority. Tasks are ready for work with all dependencies satisfied.",
  "totalClaimable": 3
}
```

#### `lodestar.task.context`

Get PRD context for a task (includes references, excerpt, and live sections).

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |
| `max_chars` | integer | No | Max characters for context (default 1000) |

**Returns:**

```json
{
  "taskId": "F001",
  "title": "Implement user authentication",
  "description": "Add email/password authentication...",
  "prdSource": "PRD.md",
  "prdRefs": [{"anchor": "## Authentication", "lines": [10, 25]}],
  "prdExcerpt": "Frozen excerpt from task creation...",
  "prdSections": [
    {"anchor": "## Authentication", "content": "Live PRD content..."}
  ],
  "drift": {
    "changed": false,
    "details": null
  },
  "content": "Combined truncated content...",
  "truncated": false,
  "warnings": []
}
```

#### `lodestar.task.claim`

Claim a task (acquires a lease).

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | Task ID to claim |
| `agent_id` | string | Yes | Agent ID (from `agent.join`) |
| `ttl_minutes` | integer | No | Lease duration in minutes (default 15) |

**Returns:**

```json
{
  "taskId": "F002",
  "leaseId": "L1234ABCD",
  "agentId": "A1234ABCD",
  "expiresAt": "2025-01-15T11:00:00Z",
  "warnings": []
}
```

!!! tip "Lock Conflict Warnings"
    If the claimed task has `locks` (file patterns) that overlap with other active leases, the response includes warnings. This helps prevent coordination conflicts.

#### `lodestar.task.release`

Release a claimed task (before completion).

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | Task ID to release |
| `agent_id` | string | Yes | Agent ID |
| `reason` | string | No | Reason for releasing (optional) |

**Returns:**

```json
{
  "taskId": "F002",
  "released": true,
  "reason": "Blocked by external dependency"
}
```

#### `lodestar.task.done`

Mark a task as done (changes status to `done`).

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |
| `agent_id` | string | Yes | Agent ID |
| `summary` | string | No | Work summary (optional) |

**Returns:**

```json
{
  "taskId": "F002",
  "status": "done",
  "completedBy": "A1234ABCD",
  "completedAt": "2025-01-15T11:30:00Z"
}
```

#### `lodestar.task.verify`

Mark a task as verified (changes status to `verified`).

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |
| `agent_id` | string | Yes | Agent ID |
| `notes` | string | No | Verification notes (optional) |

**Returns:**

```json
{
  "taskId": "F002",
  "status": "verified",
  "verifiedBy": "A1234ABCD",
  "verifiedAt": "2025-01-15T11:45:00Z"
}
```

#### `lodestar.task.complete`

**Mark a task as complete atomically** (combines `done` + `verify` in one operation).

This is the **recommended way to complete tasks** when you've finished and verified the work in the same session. It prevents tasks from being stuck in 'done' state if an agent crashes between the two operations.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |
| `agent_id` | string | Yes | Agent ID |
| `note` | string | No | Completion notes (optional) |

**Returns:**

```json
{
  "taskId": "F002",
  "status": "verified",
  "completedBy": "A1234ABCD",
  "completedAt": "2025-01-15T11:30:00Z",
  "verifiedBy": "A1234ABCD",
  "verifiedAt": "2025-01-15T11:30:00Z",
  "newlyReadyTaskIds": ["F003", "F004"]
}
```

!!! tip "When to use `task.complete` vs separate `done`+`verify`"
    - **Use `task.complete`**: When you're doing both operations in the same session and want crash protection
    - **Use `task.done` + `task.verify` separately**: When you need time between completion and verification (e.g., waiting for CI, manual testing, or handoff to another agent)

!!! warning "Atomicity"
    Unlike calling `task.done` followed by `task.verify`, `task.complete` never leaves the task in 'done' state. It updates directly from the current state to 'verified' in a single spec save operation, preventing orphaned 'done' tasks if the process crashes.

---

### Message Tools

#### `lodestar.message.send`

Send a message to another agent.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_agent_id` | string | Yes | Sending agent ID |
| `to_agent_id` | string | Yes | Recipient agent ID |
| `content` | string | Yes | Message content (max 10,000 chars) |
| `task_id` | string | No | Related task ID (optional) |
| `subject` | string | No | Message subject (optional) |

**Returns:**

```json
{
  "messageId": "M123",
  "fromAgentId": "A1234ABCD",
  "toAgentId": "A5678EFGH",
  "taskId": "F002",
  "subject": "Task handoff",
  "sentAt": "2025-01-15T11:00:00Z"
}
```

#### `lodestar.message.list`

List messages for an agent (inbox).

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_id` | string | Yes | Agent ID |
| `unread_only` | boolean | No | Only show unread messages (default false) |
| `limit` | integer | No | Max results (default 50, max 200) |

**Returns:**

```json
{
  "items": [
    {
      "messageId": "M123",
      "fromAgentId": "A5678EFGH",
      "toAgentId": "A1234ABCD",
      "taskId": "F002",
      "subject": "Task handoff",
      "content": "I've completed the authentication logic...",
      "read": false,
      "sentAt": "2025-01-15T11:00:00Z"
    }
  ],
  "total": 5,
  "unreadCount": 2
}
```

#### `lodestar.message.ack`

Mark a message as read.

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_id` | string | Yes | Agent ID |
| `message_id` | string | Yes | Message ID to acknowledge |

**Returns:**

```json
{
  "messageId": "M123",
  "read": true,
  "readAt": "2025-01-15T11:30:00Z"
}
```

---

### Event Tools

#### `lodestar.events.pull`

Pull events since a cursor for change notifications (fallback for hosts without push support).

**Inputs:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `since_cursor` | integer | No | Event ID to start after (default 0) |
| `limit` | integer | No | Max events to return (default 50, max 200) |

**Returns:**

```json
{
  "events": [
    {
      "id": 42,
      "createdAt": "2025-01-15T11:00:00Z",
      "type": "task.claimed",
      "agentId": "A1234ABCD",
      "taskId": "F002",
      "targetAgentId": null,
      "data": {"leaseId": "L1234ABCD"}
    },
    {
      "id": 43,
      "createdAt": "2025-01-15T11:15:00Z",
      "type": "message.sent",
      "agentId": "A1234ABCD",
      "taskId": "F002",
      "targetAgentId": "A5678EFGH",
      "data": {"messageId": "M123"}
    }
  ],
  "nextCursor": 43,
  "hasMore": false
}
```

**Event Types:**

- `task.claimed` - Task was claimed
- `task.released` - Task was released
- `task.done` - Task marked done
- `task.verified` - Task marked verified
- `message.sent` - Message sent
- `agent.joined` - Agent registered
- `agent.left` - Agent left

---

## MCP Resources Reference

Resources provide read-only access to repository state. They're accessible via MCP resource URIs.

### `lodestar://spec`

Returns the full `.lodestar/spec.yaml` file as text.

**MIME Type:** `text/yaml`

**Example:**

```yaml
project:
  name: my-project
  default_branch: main
tasks:
  F001:
    title: Implement user authentication
    status: verified
    ...
```

### `lodestar://status`

Returns repository status (same data as `lodestar.repo.status` tool).

**MIME Type:** `application/json`

### `lodestar://task/{taskId}`

Returns detailed task information (same data as `lodestar.task.get` tool).

**MIME Type:** `application/json`

**Example URI:** `lodestar://task/F001`

---

## Troubleshooting

### Server Won't Start

**Error:** `Not in a Lodestar repository`

**Solution:** Use `--repo /path/to/repo` to explicitly specify the repository path, or run from within a Lodestar-initialized directory.

---

**Error:** `MCP dependencies not installed`

**Solution:** Install with the `mcp` extra:

```bash
pip install 'lodestar-cli[mcp]'
# or
uv add 'lodestar-cli[mcp]'
```

---

### Testing with MCP Inspector

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) is a testing tool for MCP servers:

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Test Lodestar MCP server
mcp-inspector lodestar mcp serve --repo /path/to/repo
```

This opens a web UI where you can:

- View available tools and resources
- Call tools with custom inputs
- Inspect responses and structured output
- Monitor server logs

---

### Logs and Debugging

**View logs in stderr:**

The server logs diagnostics to stderr by default. In most MCP hosts, these appear in the extension/app console.

**Save logs to file:**

```bash
lodestar mcp serve --log-file debug.log
```

**Use JSON logs:**

```bash
lodestar mcp serve --json-logs --log-file debug.json
```

---

### Common Integration Issues

**Issue:** Tools aren't appearing in my MCP host

**Solution:** Restart the MCP host after updating the configuration. Some hosts cache server initialization.

---

**Issue:** `task.claim` returns "already claimed"

**Solution:** Check for expired leases. Use `task.list` to see lease status, or wait for the lease to expire (default 15 minutes).

---

**Issue:** Events not showing up

**Solution:** The MCP server uses a **pull model** for events. Hosts must call `lodestar.events.pull` periodically. Check your host's event polling configuration.

---

## Next Steps

- **[Error Handling Guide](guides/error-handling.md)** - Learn how to handle retriable vs non-retriable errors
- **[Agent Workflow Guide](guides/agent-workflow.md)** - Learn the full agent coordination workflow
- **[Task Commands](cli/task.md)** - CLI reference for task operations
- **[MCP Specification](https://modelcontextprotocol.io/)** - Official MCP protocol documentation
