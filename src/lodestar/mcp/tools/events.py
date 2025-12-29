"""Event tools for MCP (pull)."""

from __future__ import annotations

from mcp.types import CallToolResult

from lodestar.mcp.output import error, format_summary, with_item
from lodestar.mcp.server import LodestarContext
from lodestar.runtime.engine import get_session
from lodestar.runtime.repositories.event_repo import get_events_since_filtered


def events_pull(
    context: LodestarContext,
    since_cursor: int = 0,
    limit: int = 200,
    filter_types: list[str] | None = None,
) -> CallToolResult:
    """
    Pull events from the event stream.

    Provides pull-based event streaming for hosts without reliable push support.
    Returns events since a given cursor (event ID) with optional type filtering.

    Args:
        context: Lodestar server context
        since_cursor: Event ID cursor - returns events after this ID (default: 0)
        limit: Maximum number of events to return (default: 200, max: 1000)
        filter_types: Optional list of event types to filter by (default: None)

    Returns:
        CallToolResult with events array and nextCursor for pagination
    """
    # Validate limit
    if limit < 1:
        return error(
            "limit must be at least 1",
            error_code="INVALID_LIMIT",
            details={"limit": limit, "min": 1},
        )

    if limit > 1000:
        return error(
            "limit exceeds maximum of 1000",
            error_code="LIMIT_TOO_LARGE",
            details={"limit": limit, "max": 1000},
        )

    # Validate since_cursor
    if since_cursor < 0:
        return error(
            "since_cursor must be non-negative",
            error_code="INVALID_CURSOR",
            details={"since_cursor": since_cursor},
        )

    # Fetch events from database
    # Note: We fetch limit + 1 to determine if there are more events (for cursor)
    with get_session(context.db._session_factory) as session:
        events = get_events_since_filtered(
            session=session,
            since_event_id=since_cursor,
            limit=limit + 1,
            filter_types=filter_types,
        )

    # Determine if there are more events (for pagination)
    has_more = len(events) > limit
    if has_more:
        # Remove the extra event we fetched for pagination check
        events = events[:limit]

    # Determine next cursor
    next_cursor = events[-1].event_id if has_more and events else None

    # Format events for response
    formatted_events = []
    for event in events:
        formatted_event = {
            "id": event.event_id,
            "createdAt": event.created_at,
            "type": event.event_type,
        }

        # Add optional fields if present
        if event.agent_id:
            formatted_event["actorAgentId"] = event.agent_id
        if event.task_id:
            formatted_event["taskId"] = event.task_id
        if event.target_agent_id:
            formatted_event["targetAgentId"] = event.target_agent_id
        if event.data:
            formatted_event["payload"] = event.data

        formatted_events.append(formatted_event)

    # Build summary
    count_str = f"{len(formatted_events)} event{'s' if len(formatted_events) != 1 else ''}"
    filter_parts = []
    if filter_types:
        filter_parts.append(f"filtered by {len(filter_types)} type(s)")
    summary = format_summary(
        "Pulled",
        count_str,
        " ".join(filter_parts) if filter_parts else None,
    )

    # Build response
    response_data = {
        "ok": True,
        "events": formatted_events,
        "count": len(formatted_events),
    }

    if next_cursor is not None:
        response_data["nextCursor"] = next_cursor

    return with_item(summary, item=response_data)


def register_event_tools(mcp: object, context: LodestarContext) -> None:
    """
    Register event tools with the FastMCP server.

    Args:
        mcp: FastMCP server instance
        context: Lodestar context to use for all tools
    """

    @mcp.tool(name="lodestar_events_pull")
    def pull_tool(
        since_cursor: int = 0,
        limit: int = 200,
        filter_types: list[str] | None = None,
    ) -> CallToolResult:
        """Pull events from the event stream.

        Provides pull-based event streaming for hosts without reliable push support.
        Returns events in chronological order starting after the given cursor (event ID).

        Args:
            since_cursor: Event ID cursor - returns events with ID > this value (default: 0)
            limit: Maximum number of events to return (default: 200, max: 1000)
            filter_types: Optional list of event types to filter by (optional)

        Returns:
            Success response with:
            - events: Array of event objects with fields (id, createdAt, type, actorAgentId, taskId, targetAgentId, payload)
            - count: Number of events returned
            - nextCursor: Event ID to use for next page (if more events available)

            Returns error if limit is invalid or cursor is negative.
        """
        return events_pull(
            context=context,
            since_cursor=since_cursor,
            limit=limit,
            filter_types=filter_types,
        )
