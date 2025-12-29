# Lodestar - Future Improvements

## UX Improvements

### Consistent CLI Parameter Patterns

**Problem**: The CLI has inconsistent parameter requirements across task commands, which can lead to user errors:

- `lodestar task next` - Does NOT accept `--agent` parameter
- `lodestar task claim <id> --agent <id>` - REQUIRES `--agent` parameter
- `lodestar task done <id>` - Does NOT require `--agent` (infers from lease)
- `lodestar task verify <id> --agent <id>` - REQUIRES `--agent` parameter
- `lodestar task release <id> --agent <id>` - REQUIRES `--agent` parameter

This inconsistency causes confusion, especially when switching between commands.

**Suggested Solutions**:

1. **Option A: Make `--agent` consistent across all commands**
   - Add optional `--agent` to `task next` for filtering/personalization
   - Make `--agent` required on all mutation commands (done, verify, release)
   - Benefits: Predictable, explicit, less ambiguous
   - Drawbacks: More verbose for single-agent workflows

2. **Option B: Add better error messages**
   - When a command is called without required `--agent`, suggest:
     ```
     Error: --agent is required for this command.
     
     Tip: You can save your agent ID as an environment variable:
       export LODESTAR_AGENT_ID=<your-id>
       # or on Windows: $env:LODESTAR_AGENT_ID = "<your-id>"
     ```
   - Commands could read from `LODESTAR_AGENT_ID` env var as fallback

3. **Option C: Interactive agent selection**
   - If `--agent` is missing and `LODESTAR_AGENT_ID` is not set:
     ```
     No agent specified. Select an agent:
     1. Agent-A1B2C3D (last active: 2m ago)
     2. Agent-X7Y8Z9W (last active: 1h ago)
     3. Create new agent
     
     Choice: _
     ```
   - Only in interactive mode (not when `--json` is used)

4. **Option D: Command-specific defaults**
   - `task next` could accept optional `--agent` for future personalization features
   - Add `--agent` to schema but make it optional with clear help text
   - Commands that require `--agent` could look for the last active agent from runtime DB

**Recommendation**: Implement **Option B** (env var support) + partial **Option A** (make `--agent` consistent where needed). This provides:
- Environment variable for convenience: `LODESTAR_AGENT_ID`
- Clear error messages with suggestions
- Consistent parameter patterns across similar commands
- Backward compatibility with explicit flags

**Priority**: Medium - Impacts developer experience but has workarounds

---

## Other Ideas

(Add future improvement ideas below)
