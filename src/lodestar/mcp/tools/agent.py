"""Agent management tools for MCP."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mcp.types import CallToolResult

from lodestar.mcp.output import error, format_summary, success
from lodestar.mcp.server import LodestarContext
from lodestar.mcp.validation import validate_agent_id, validate_ttl
from lodestar.models.runtime import DEFAULT_IDLE_THRESHOLD_MINUTES, Agent


def agent_join(
    context: LodestarContext,
    name: str | None = None,
    client: str | None = None,
    model: str | None = None,
    capabilities: list[str] | None = None,
    ttl_seconds: int | None = None,
) -> CallToolResult:
    """
    Register as an agent and get identity.

    This is the canonical entrypoint for agents. This is the only mutating
    tool that doesn't require an agentId parameter.

    Args:
        context: Lodestar server context
        name: Display name for this agent (optional)
        client: Client name (e.g., 'claude-desktop', 'vscode') (optional)
        model: Model name (e.g., 'claude-3.5-sonnet') (optional)
        capabilities: List of agent capabilities (optional)
        ttl_seconds: Default TTL for leases in seconds (optional)

    Returns:
        CallToolResult with agent ID and registration details
    """
    # Build session metadata
    session_meta = {}
    if model:
        session_meta["model"] = model
    if client:
        session_meta["client"] = client

    # Validate and set TTL
    validated_ttl = validate_ttl(ttl_seconds)

    # Create and register agent
    agent = Agent(
        display_name=name or "",
        role="",  # Role not exposed in MCP interface
        capabilities=capabilities or [],
        session_meta=session_meta,
    )
    context.db.register_agent(agent)

    # Get claimable task count for context
    context.reload_spec()
    claimable_count = len(context.spec.get_claimable_tasks())

    # Get current server time
    server_time = datetime.now(UTC).isoformat()

    # Build structured data
    data = {
        "agentId": agent.agent_id,
        "displayName": agent.display_name,
        "capabilities": agent.capabilities,
        "registeredAt": agent.created_at.isoformat(),
        "sessionMeta": session_meta,
        "leaseDefaults": {
            "ttlSeconds": validated_ttl,
        },
        "serverTime": server_time,
        "notes": [
            f"{claimable_count} tasks available to claim",
            "Use task.next to find claimable tasks",
            "Remember to renew leases before they expire",
        ],
    }

    # Build summary
    summary = format_summary(
        "Registered as agent",
        agent.agent_id,
        f"({claimable_count} tasks available)",
    )

    return success(summary, data=data)


def agent_heartbeat(
    context: LodestarContext,
    agent_id: str,
) -> CallToolResult:
    """
    Update agent heartbeat timestamp.

    Refreshes the agent's last_seen_at timestamp to indicate the agent
    is still active.

    Args:
        context: Lodestar server context
        agent_id: Agent ID to update (required)

    Returns:
        CallToolResult with heartbeat update confirmation
    """
    # Validate agent ID
    try:
        validated_agent_id = validate_agent_id(agent_id)
    except Exception as e:
        return error(str(e), error_code="INVALID_AGENT_ID")

    # Update heartbeat
    success_update = context.db.update_heartbeat(validated_agent_id)

    if not success_update:
        return error(
            f"Agent {validated_agent_id} not found",
            error_code="AGENT_NOT_FOUND",
            details={"agent_id": validated_agent_id},
        )

    # Calculate when agent will be considered idle (expires at)
    # Agents become idle after DEFAULT_IDLE_THRESHOLD_MINUTES of inactivity
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=DEFAULT_IDLE_THRESHOLD_MINUTES)

    # Build structured data
    data = {
        "agentId": validated_agent_id,
        "updated": True,
        "expiresAt": expires_at.isoformat(),
        "warnings": [],
    }

    # Add warning if agent should send heartbeats more frequently
    # Recommend heartbeat at half the idle threshold to maintain active status
    recommended_interval = DEFAULT_IDLE_THRESHOLD_MINUTES / 2
    data["warnings"].append(
        f"Send heartbeat every {recommended_interval:.0f} minutes to maintain active status"
    )

    summary = format_summary("Updated heartbeat for", validated_agent_id)

    return success(summary, data=data)


def agent_leave(
    context: LodestarContext,
    agent_id: str,
    reason: str | None = None,
) -> CallToolResult:
    """
    Mark agent as offline gracefully.

    Marks the agent as offline and logs the leave event. Agents marked offline
    will have their status set to OFFLINE and will no longer appear in active
    agent listings.

    Args:
        context: Lodestar server context
        agent_id: Agent ID to mark offline (required)
        reason: Optional reason for leaving

    Returns:
        CallToolResult with confirmation
    """
    # Validate agent ID
    try:
        validated_agent_id = validate_agent_id(agent_id)
    except Exception as e:
        return error(str(e), error_code="INVALID_AGENT_ID")

    # Mark agent offline
    success_update = context.db.mark_agent_offline(validated_agent_id, reason)

    if not success_update:
        return error(
            f"Agent {validated_agent_id} not found",
            error_code="AGENT_NOT_FOUND",
            details={"agent_id": validated_agent_id},
        )

    # Get agent's active leases count
    active_leases = context.db.get_agent_leases(validated_agent_id, active_only=True)
    active_count = len(active_leases)

    # Build structured data
    data = {
        "agentId": validated_agent_id,
        "markedOffline": True,
        "reason": reason,
        "warnings": [],
    }

    # Warn if agent has active leases
    if active_count > 0:
        data["warnings"].append(
            f"Agent has {active_count} active lease(s) that will expire naturally"
        )
        data["activeLeases"] = active_count

    summary_parts = ["Marked agent offline:", validated_agent_id]
    if reason:
        summary_parts.append(f"(reason: {reason})")

    summary = " ".join(summary_parts)

    return success(summary, data=data)


def register_agent_tools(mcp: object, context: LodestarContext) -> None:
    """
    Register agent management tools with the FastMCP server.

    Args:
        mcp: FastMCP server instance
        context: Lodestar context to use for all tools
    """

    @mcp.tool(name="lodestar.agent.join")
    def join_tool(
        name: str | None = None,
        client: str | None = None,
        model: str | None = None,
        capabilities: list[str] | None = None,
        ttl_seconds: int | None = None,
    ) -> CallToolResult:
        """Register as an agent and get your identity.

        This is the canonical entrypoint for agents. Call this first to register
        and get your agent ID, then use that ID for all subsequent operations.

        Args:
            name: Optional display name for this agent
            client: Optional client name (e.g., 'claude-desktop', 'vscode')
            model: Optional model name (e.g., 'claude-3.5-sonnet')
            capabilities: Optional list of agent capabilities
            ttl_seconds: Optional default TTL for leases in seconds (60-7200)

        Returns:
            Agent ID and registration details including lease defaults
        """
        return agent_join(
            context=context,
            name=name,
            client=client,
            model=model,
            capabilities=capabilities,
            ttl_seconds=ttl_seconds,
        )

    @mcp.tool(name="lodestar.agent.heartbeat")
    def heartbeat_tool(agent_id: str) -> CallToolResult:
        """Update agent heartbeat timestamp.

        Refreshes the agent's presence to indicate it is still active.
        Agents should send heartbeats regularly to maintain active status.

        Args:
            agent_id: Agent ID to update (required)

        Returns:
            Heartbeat update confirmation with expiration time
        """
        return agent_heartbeat(context=context, agent_id=agent_id)

    @mcp.tool(name="lodestar.agent.leave")
    def leave_tool(agent_id: str, reason: str | None = None) -> CallToolResult:
        """Mark agent as offline gracefully.

        Marks the agent as offline and logs the leave event. Use this when
        an agent is done working and wants to cleanly disconnect.

        Args:
            agent_id: Agent ID to mark offline (required)
            reason: Optional reason for leaving

        Returns:
            Confirmation with any warnings about active leases
        """
        return agent_leave(context=context, agent_id=agent_id, reason=reason)
