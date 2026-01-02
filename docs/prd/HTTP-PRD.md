# PRD: Streamable HTTP Transport for MCP Server

## Overview

Add streamable HTTP transport to the Lodestar MCP server, enabling multiple agents in parallel coding sessions to connect to a single MCP server instance. This solves the limitation of stdio transport where each agent requires its own subprocess.

## Problem Statement

With stdio transport:
- Each MCP client spawns a separate server subprocess
- Multiple agents cannot share state or coordinate through a single server
- No way to run a persistent MCP service that multiple VS Code windows can connect to

## Solution

Implement the [MCP Streamable HTTP Transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) specification, allowing the MCP server to run as an HTTP service on localhost.

## User Experience

### Starting the Server

```bash
# stdio (current default, unchanged)
lodestar mcp serve

# Streamable HTTP (new)
lodestar mcp serve --transport streamable-http
lodestar mcp serve --transport streamable-http --port 8080
lodestar mcp serve --transport streamable-http --host 127.0.0.1 --port 8000
```

### Client Configuration

Clients connect to `http://127.0.0.1:8000/mcp` (or configured host:port).

Example VS Code MCP client config:
```json
{
  "mcpServers": {
    "lodestar": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

## Technical Requirements

### TR-1: CLI Transport Options

Add CLI options to `lodestar mcp serve`:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--transport` / `-t` | enum | `stdio` | Transport type: `stdio` or `streamable-http` |
| `--host` | string | `127.0.0.1` | HTTP bind address (streamable-http only) |
| `--port` | int | `8000` | HTTP port (streamable-http only) |

**Acceptance Criteria:**
- `--host` and `--port` are ignored when transport is `stdio`
- Server binds only to localhost by default (security)
- Clear error message if port is already in use

### TR-2: Lifespan Management

Implement proper startup/shutdown lifecycle:

**On Startup:**
1. Initialize shared `McpContext` with repository root
2. Run `cleanup_orphaned_leases()` to clear stale leases
3. Run `cleanup_temp_files()` to remove old temp files
4. Log server URL and ready status

**On Shutdown:**
1. Call `context.db.dispose()` to close database connections
2. Log clean shutdown message

**Acceptance Criteria:**
- Graceful handling of SIGTERM and SIGINT
- No orphaned database connections after shutdown
- Startup logs show listening URL

### TR-3: Shared Context with Thread-Safe Database

Use a single shared `McpContext` for all HTTP sessions:

- SQLite WAL mode already enables concurrent reads
- 5-second busy timeout handles write contention
- Add optional connection pooling (`QueuePool`) for HTTP mode

**Acceptance Criteria:**
- Multiple concurrent tool calls execute without deadlock
- No "database is locked" errors under normal load
- Existing NullPool behavior preserved for stdio mode

### TR-4: Transport Implementation

Use FastMCP's built-in streamable HTTP support:

```python
if transport == "streamable-http":
    mcp.settings.host = host
    mcp.settings.port = port
    mcp.run(transport="streamable-http")
else:
    mcp.run(transport="stdio")
```

**Acceptance Criteria:**
- Server responds to POST requests with JSON-RPC
- Server supports SSE for streaming responses
- Session management via `MCP-Session-Id` header works correctly

### TR-5: Documentation

Update `docs/mcp.md` with:

1. HTTP transport usage examples
2. Multi-agent configuration patterns
3. Client configuration examples (VS Code, Claude Desktop)
4. Security notes (localhost binding, no auth requirement)

**Acceptance Criteria:**
- Examples are copy-paste ready
- Security considerations documented
- Troubleshooting section for common issues

### TR-6: Integration Testing

Add test for concurrent HTTP access:

1. Start MCP server with streamable-http transport
2. Spawn 3+ parallel clients
3. Each client makes simultaneous tool calls
4. Verify all responses are correct (no cross-talk)
5. Verify no database errors

**Acceptance Criteria:**
- Test passes reliably (no flaky failures)
- Test completes in <30 seconds
- Covers at least: agent.list, task.list, task.claim

## Security Considerations

- **Localhost only**: Default bind to `127.0.0.1` prevents remote access
- **No authentication**: Acceptable for local dev use; auth deferred to future work
- **Origin validation**: FastMCP/Starlette handles Origin header validation

## Dependencies

No new dependencies required. `mcp>=1.0.0` already bundles:
- `uvicorn>=0.31.1` - ASGI server
- `starlette>=0.27` - HTTP framework
- `sse-starlette>=1.6.1` - SSE support

## Out of Scope

- Authentication/authorization (deferred)
- Remote/non-localhost access
- WebSocket transport
- Load balancing / multi-instance

## Task Breakdown

| ID | Title | Depends On |
|----|-------|------------|
| HTTP-01 | Add transport CLI options | - |
| HTTP-02 | Implement lifespan context manager | - |
| HTTP-03 | Add connection pooling option | - |
| HTTP-04 | Wire up transport branching | HTTP-01, HTTP-02, HTTP-03 |
| HTTP-05 | Update MCP documentation | HTTP-04 |
| HTTP-06 | Add concurrent access integration test | HTTP-04 |
