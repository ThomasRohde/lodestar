# PRD — Lodestar MCP Server (stdio)

Date: 2025-12-28
Status: Draft (implementation-ready)

## Summary

Lodestar is a Python CLI that coordinates multiple agents working in the same Git repository via a two-plane state model: task definitions in `.lodestar/spec.yaml` (committed) and execution state in `.lodestar/runtime.sqlite` (gitignored). It supports atomic task claiming with leases, dependency-aware readiness, and inter-agent messaging. 

This PRD specifies an **MCP server** for Lodestar that exposes Lodestar’s core operations as MCP **tools**, and exposes read-only state as MCP **resources**, over the **stdio transport**. The result is that MCP-capable coding agents (VS Code / Visual Studio / Claude Desktop / others) can coordinate through Lodestar **without shelling out to the CLI**, and can receive **real-time-ish updates** via MCP notifications, with a **pull fallback** for MCP hosts that don’t reliably surface server→client notifications.

References (protocol):
- MCP Tools spec incl. `notifications/tools/list_changed` (2025-06-18): https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- MCP stdio transport framing (2025-06-18): https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
- MCP logging (`notifications/message`) (2025-06-18): https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/logging
- MCP progress notifications (2025-06-18): https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress
- MCP Python SDK (FastMCP): https://modelcontextprotocol.github.io/python-sdk/

## What you’re really trying to achieve (the underlying goal)

The goal isn’t “implement MCP” for its own sake. The goal is:
1) make agent coordination **native** inside MCP hosts (no shell / no custom glue), and  
2) reduce polling by enabling **push-style signals** (“new message”, “task unblocked”, “lease expiring”), while still working in hosts with partial push support.

This PRD explicitly designs for both: notifications where supported, and a robust `events.pull` fallback when not.

## Goals

1. Provide an MCP server that runs locally via **stdio** and exposes Lodestar operations as MCP **tools**.
2. Support MCP hosts that implement the full spec: structured outputs, progress, logging, and notifications.
3. Provide **event-driven updates** (notifications) for changes to: messages, task status, claim/lease state.
4. Provide a **pull fallback** (event cursor API) so coordination still works when notifications are not surfaced.
5. Reuse existing Lodestar application logic (the same services used by the CLI), not duplicate behavior.

## Non-goals

- No remote transport (Streamable HTTP / SSE) in v1 (stdio only).
- No “multi-repo dashboard” or centralized coordinator; this remains local-per-repo.
- No new storage model; continue using `.lodestar/spec.yaml` + `.lodestar/runtime.sqlite`.
- No attempt to “make every CLI flag available”; only the coordination primitives needed by agents.

## Users & key scenarios

- Coding agent in an MCP host wants to:
  - join as an agent identity
  - find the next task that is ready
  - claim a task (lease)
  - read task context (PRD excerpt) and requirements
  - mark done + verify
  - message other agents for handoffs
  - observe updates without polling (or poll efficiently if push is unavailable)

## Product requirements

### R1. Stdio MCP server
- The server MUST run over stdio (JSON-RPC messages delimited by newlines; stdout is protocol; stderr is logs).
- The server MUST not emit non-protocol output on stdout.

### R2. Repo targeting
- The server MUST operate on exactly one repository at a time.
- The server MUST support selecting a repo root explicitly (e.g. `--repo /path/to/repo`) because many MCP hosts launch servers from an arbitrary working directory.
- If repo root is not provided, the server SHOULD discover the repo root by walking upwards from CWD until a `.lodestar/` directory is found; otherwise return a clear error in tool results.

### R3. Structured outputs (agent-friendly)
- Every tool SHOULD return:
  - a human-readable text summary (for debugging / clients that ignore structured results)
  - `structuredContent` that is machine-parseable
  - an `outputSchema` for stable integration where possible

### R4. Event updates (push + pull)
- The server SHOULD emit MCP notifications for changes where feasible:
  - `notifications/message` for log-style messages
  - `notifications/progress` for long-running tool calls when the client requests progress
  - (optional) `notifications/tools/list_changed` only if tool definitions change at runtime (likely false in v1)
- The server MUST provide a pull-based events API tool: `lodestar.events.pull(since_cursor)`.

### R5. Safety & input validation
- Tools MUST validate inputs and enforce reasonable size limits (message length, lists, etc.).
- Mutating tools MUST require a valid `agent_id` (except `agent.join`).

### R6. Compatibility targets
- The server MUST work with MCP Inspector and at least one “full spec” host (VS Code or Visual Studio are the likely primary targets).
- For hosts with partial push support, the `events.pull` tool MUST make the system still usable.

## High-level architecture

### Server runtime model
- MCP host launches `lodestar mcp serve ...` as a subprocess.
- Lodestar MCP server initializes:
  1) repo root resolution
  2) open/create runtime DB connection
  3) instantiate Lodestar “application services” (the same logic the CLI calls)
  4) start an optional background watcher loop that tails a DB-backed event stream and emits notifications

### Event stream design (runtime.sqlite)
Add a runtime table to persist events (if something equivalent doesn’t already exist):

`events`
- `id` INTEGER PRIMARY KEY (monotonic cursor)
- `created_at` TEXT (ISO8601)
- `type` TEXT (e.g. `task.claimed`, `task.done`, `task.verified`, `message.sent`, `lease.expired`, `agent.joined`)
- `actor_agent_id` TEXT NULL
- `task_id` TEXT NULL
- `target_agent_id` TEXT NULL
- `payload_json` TEXT (small JSON blob)
- `correlation_id` TEXT (tool call id / trace id)

Rules:
- Every mutating operation MUST append at least one event.
- Some derived events MAY be generated (e.g. lease-expired) during reads or housekeeping.

Notification rules:
- If a client supports push, server SHOULD emit a lightweight `notifications/message` or a custom “status” log when events occur.
- Regardless of push support, clients can always call `lodestar.events.pull`.

## MCP surface area

### Tool naming convention
Use dotted tool names so hosts can group them:
- `lodestar.repo.*`
- `lodestar.agent.*`
- `lodestar.task.*`
- `lodestar.message.*`
- `lodestar.events.*`

### Tools (v1)

Below are the **minimum viable** tools for agent coordination. All tools return both text and structured results.

#### 1) `lodestar.repo.status`
Purpose: “Where are we?” summary for humans/agents.

Input:
- `repo` (optional): explicit repo root path

Output (structured):
- repoRoot
- specPath
- runtimePath
- counts: tasks by status, active leases, agents online, unread messages
- suggestedNextActions: array of strings

#### 2) `lodestar.agent.join`
Purpose: register/announce an agent identity.

Input:
- `name` (optional): display name
- `client` (optional): host name/version (e.g. “vscode”, “claude-code”)
- `model` (optional): model identifier if known
- `capabilities` (optional): { "supportsPush": true, "supportsProgress": true, ... }
- `ttlSeconds` (optional): desired heartbeat TTL; server may clamp

Output:
- agentId
- leaseDefaults: { ttlSeconds }
- serverTime
- notes (any caveats)

#### 3) `lodestar.agent.heartbeat`
Purpose: keep agent alive and refresh presence.

Input:
- agentId (required)

Output:
- ok (bool)
- expiresAt
- warnings (e.g. “agent unknown”, “runtime locked”, etc.)

#### 4) `lodestar.agent.leave`
Purpose: mark agent offline gracefully.

Input:
- agentId (required)
- reason (optional)

Output:
- ok (bool)

#### 5) `lodestar.task.list`
Purpose: list tasks with filters.

Input:
- `status` (optional): ready|done|verified|deleted|all
- `label` (optional)
- `limit` (optional, default 50, max 200)
- `cursor` (optional): pagination cursor (server-defined)

Output:
- tasks: array of TaskSummary
- nextCursor: optional

TaskSummary:
- id, title, status, priority, labels[]
- dependencies: ids[]
- claimedByAgentId?: string
- leaseExpiresAt?: string
- updatedAt?: string

#### 6) `lodestar.task.get`
Purpose: fetch a single task (spec + runtime state + PRD context pointers).

Input:
- taskId (required)

Output:
- task: TaskDetail (includes description, acceptance criteria, PRD context fields, dependency graph info)
- runtime: status, claimedBy, lease, timestamps
- warnings: drift detection or missing PRD source, etc.

#### 7) `lodestar.task.next`
Purpose: dependency-aware “what should I do next?”

Input:
- agentId (optional): if provided, allow personalization (avoid already-claimed tasks; prefer matching labels)
- limit (optional, default 5, max 20)

Output:
- candidates: TaskSummary[] (already filtered to claimable ready tasks)
- rationale: short explanation text (also in structured form)

#### 8) `lodestar.task.claim`
Purpose: claim a task with a lease.

Input:
- taskId (required)
- agentId (required)
- ttlSeconds (optional): desired TTL; server clamps to configured bounds
- force (optional): if true, attempt claim even if a lease exists, only if it’s expired

Output:
- ok
- lease: { taskId, agentId, expiresAt, ttlSeconds }
- conflict?: { claimedByAgentId, expiresAt } when ok=false

#### 9) `lodestar.task.release`
Purpose: release a claim (before TTL expiry).

Input:
- taskId (required)
- agentId (required)
- reason (optional)

Output:
- ok
- previousLease?: { ... }

#### 10) `lodestar.task.done`
Purpose: mark task done (work completed, pending verification).

Input:
- taskId (required)
- agentId (required)
- note (optional): completion note

Output:
- ok
- status: done
- warnings: e.g. “not claimed by you” (policy-defined)

#### 11) `lodestar.task.verify`
Purpose: mark task verified (unblocks dependent tasks).

Input:
- taskId (required)
- agentId (required)
- note (optional)

Output:
- ok
- status: verified
- newlyReadyTaskIds: string[]

#### 12) `lodestar.task.context`
Purpose: deliver “just enough PRD context” (as Lodestar already supports).

Input:
- taskId (required)

Output:
- context: { prdSource, prdRef, prdExcerpt, drift?: { changed: bool, details?: ... } }

#### 13) `lodestar.message.send`
Purpose: inter-agent messaging.

Input:
- fromAgentId (required)
- toAgentId (optional): if omitted, broadcast to all agents
- taskId (optional): link message to task
- subject (optional)
- body (required, max length enforced)
- severity (optional): info|warning|handoff|blocker

Output:
- ok
- messageId
- deliveredTo: agentIds[] (best-effort)

#### 14) `lodestar.message.list`
Purpose: fetch messages for an agent.

Input:
- agentId (required)
- unreadOnly (optional, default true)
- limit (optional, default 50, max 200)
- sinceId (optional): for incremental consumption

Output:
- messages: array of { id, createdAt, from, to, taskId?, subject?, body, severity, readAt? }
- nextCursor?: optional

#### 15) `lodestar.message.ack`
Purpose: mark message(s) read.

Input:
- agentId (required)
- messageIds (required list)

Output:
- ok
- updated: count

#### 16) `lodestar.events.pull`
Purpose: pull event stream when notifications are unreliable.

Input:
- sinceCursor (optional, default 0)
- limit (optional, default 200, max 1000)
- filterTypes (optional): string[]

Output:
- events: array of { id, createdAt, type, actorAgentId?, taskId?, targetAgentId?, payload }
- nextCursor: last event id returned

### Resources (v1)

Expose read-only data via MCP resources to allow clients to fetch without “tool approval” flows (host dependent).

- `lodestar://spec`
  - Returns the content of `.lodestar/spec.yaml` as text (mime `text/yaml`).
- `lodestar://task/{taskId}`
  - Returns a JSON representation of a task (mime `application/json`).
- `lodestar://status`
  - Returns JSON summary similar to `repo.status` (mime `application/json`).

Notes:
- Resources are read-only; any mutation MUST be done via tools.

### Prompts (optional, v1.1)
Provide a small set of prompt templates to make hosts “self-explanatory”:
- `lodestar_agent_workflow`: a short workflow recipe (join → next → claim → context → done → verify → message handoff).
- `lodestar_task_execute`: asks the agent to follow acceptance criteria and produce a verification checklist.

This is optional because not all hosts surface prompts well; tools are the main integration point.

## Notifications behavior

### Logging
- Use MCP `notifications/message` to emit structured logs (level, logger name, and data).

### Progress
- If the client provides a progress token in request metadata, long-running operations SHOULD emit `notifications/progress` updates.
- Likely “long” operations in Lodestar: `task.verify` when it performs validation or expensive graph work (even if currently quick, design for future).

### Push updates
Because not all hosts reliably surface server→client notifications to the LLM, treat push as best-effort:
- On event write, server SHOULD:
  - emit a `notifications/message` with a compact summary and/or
  - emit a resource-changed hint (if implemented by the SDK/host pair)

Clients that ignore push can use `events.pull` efficiently.

## CLI / packaging requirements

### New command
Add a new CLI group:
- `lodestar mcp serve [--repo PATH] [--stdio] [--log-file PATH] [--json-logs] [--dev]`

Defaults:
- `--stdio` is the default transport (and only supported in v1).
- server logs go to stderr; optionally also to a file.

### Dependencies
- Add the official MCP Python SDK (`mcp`) as a dependency, ideally as an optional extra:
  - `lodestar-cli[mcp]`
- The executable `lodestar` should include the `mcp` extra in published distribution if you want MCP support by default (decision: ship by default vs optional).

### Documentation
- Add `docs/mcp.md` explaining:
  - how to run `lodestar mcp serve`
  - example host configurations (VS Code / Claude Desktop)
  - troubleshooting (where stderr logs go; how to test with MCP Inspector)

## Security & safety considerations

- All inputs MUST be validated.
- Tool descriptions MUST avoid suggesting unsafe actions.
- Enforce bounds:
  - max message length (e.g. 16KB)
  - max list limits
  - TTL clamp for leases (e.g. min 60s, max 2h)
- Enforce that mutating tools require `agentId` that exists (or auto-join policy, but keep strict in v1).
- Never execute arbitrary shell commands as part of MCP tools in v1.

## Acceptance criteria

1. `lodestar mcp serve --repo <repo>` starts and completes MCP initialization successfully in MCP Inspector.
2. MCP client can list tools and invoke:
   - join → next → claim → get/context → done → verify
3. Task state transitions reflect correctly in `.lodestar/runtime.sqlite` and unblock dependencies.
4. Two MCP clients connected to the same repo can coordinate:
   - client A claims a task, client B cannot claim it until released/expired
   - client A sends message to B, B can read + ack it
5. `events.pull` returns a monotonic event stream and allows incremental consumption.
6. Logging notifications and stderr logs show meaningful diagnostics without polluting stdout.
7. A “partial push” host can still function by polling `events.pull` periodically.

## Implementation plan (phased)

### Phase 1 — MVP MCP server (tools only)
- Add `lodestar mcp serve`
- Implement tools for: status, agent join/heartbeat, task list/get/next/claim/release/done/verify/context, message send/list/ack, events.pull
- Implement event table and append-on-mutation hooks

### Phase 2 — Notifications and nicer UX
- Add structured logging via `notifications/message`
- Add progress support for long operations
- Add background watcher loop to emit push hints on new events

### Phase 3 — Resources + prompts
- Implement resources (spec, status, task)
- Add optional prompts

## Testing strategy

Unit tests:
- Tool input validation (bad ids, bad TTLs, missing repo, etc.)
- Output schemas (structuredContent matches expected types)

Integration tests:
- Spawn the MCP server subprocess and connect with an MCP client library (Python) over stdio.
- Run concurrent claims from two client sessions against a shared repo fixture.

Manual acceptance:
- MCP Inspector connection and tool calls
- At least one real host (VS Code or Visual Studio)

## Open questions (decide during implementation)
1. Should `lodestar mcp` be included in default install, or behind `lodestar-cli[mcp]`?
2. How strict should `task.done/verify` be about “must be claimed by the same agent”?
3. Should the server auto-join an agent if `agentId` is missing, or keep strict? (Recommendation: strict in v1.)
4. Should the server support a “machine-wide runtime” path to coordinate across git worktrees, or keep current worktree-local runtime? (Non-goal for this PRD; revisit separately.)

---
End of PRD
