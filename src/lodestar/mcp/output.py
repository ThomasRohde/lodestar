"""Structured output helpers for MCP tool responses.

This module provides utilities for creating consistent, structured
responses from MCP tools. Every tool response includes:
- Human-readable text summary
- Machine-parseable structured content
- Optional metadata

All responses follow the CallToolResult format for MCP protocol compliance.
"""

from __future__ import annotations

from typing import Any

from mcp.types import CallToolResult, TextContent


def success(
    summary: str,
    data: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> CallToolResult:
    """
    Create a successful tool response with structured output.

    Args:
        summary: Human-readable description of the result
        data: Machine-parseable structured data (optional)
        meta: Hidden metadata for client applications (optional)

    Returns:
        CallToolResult with text content and optional structured data

    Example:
        >>> success(
        ...     "Created task T123",
        ...     data={"task_id": "T123", "status": "ready"},
        ...     meta={"created_at": "2024-01-01T00:00:00Z"}
        ... )
    """
    result = CallToolResult(
        content=[TextContent(type="text", text=summary)],
    )

    if data is not None:
        result.structuredContent = data

    if meta is not None:
        result._meta = meta

    return result


def error(
    message: str,
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
    retriable: bool = False,
    suggested_action: str | None = None,
    current_state: dict[str, Any] | None = None,
) -> CallToolResult:
    """
    Create an error tool response with structured output.

    Args:
        message: Human-readable error message
        error_code: Machine-readable error code (optional)
        details: Additional error details (optional)
        retriable: Whether this error is transient and can be retried (optional, default False)
        suggested_action: Suggested action for recovery (optional)
        current_state: Partial state information even on failure (optional)

    Returns:
        CallToolResult with error information

    Example:
        >>> error(
        ...     "File system lock detected",
        ...     error_code="SPEC_LOCK_ERROR",
        ...     details={"timeout": 5.0},
        ...     retriable=True,
        ...     suggested_action="retry_immediately",
        ...     current_state={"task_status": "done"}
        ... )
    """
    structured_data: dict[str, Any] = {
        "error": message,
        "retriable": retriable,
    }

    if error_code is not None:
        structured_data["error_code"] = error_code

    if details is not None:
        structured_data["details"] = details

    if suggested_action is not None:
        structured_data["suggested_action"] = suggested_action

    if current_state is not None:
        structured_data["current_state"] = current_state

    return CallToolResult(
        content=[TextContent(type="text", text=f"Error: {message}")],
        structuredContent=structured_data,
        isError=True,
    )


def with_list(
    summary: str,
    items: list[dict[str, Any]],
    total: int | None = None,
    next_cursor: str | None = None,
    meta: dict[str, Any] | None = None,
) -> CallToolResult:
    """
    Create a tool response containing a list of items.

    Args:
        summary: Human-readable description (e.g., "Found 5 tasks")
        items: List of structured items
        total: Total count if different from len(items) (for pagination)
        next_cursor: Cursor for fetching next page of results (optional)
        meta: Hidden metadata for client applications (optional)

    Returns:
        CallToolResult with list data

    Example:
        >>> with_list(
        ...     "Found 2 tasks",
        ...     items=[
        ...         {"id": "T001", "title": "First"},
        ...         {"id": "T002", "title": "Second"},
        ...     ],
        ...     total=10,  # If showing page 1 of multiple pages
        ...     next_cursor="T002",  # Use this to get the next page
        ... )
    """
    structured_data: dict[str, Any] = {
        "items": items,
        "count": len(items),
    }

    if total is not None:
        structured_data["total"] = total

    if next_cursor is not None:
        structured_data["nextCursor"] = next_cursor

    result = CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structuredContent=structured_data,
    )

    if meta is not None:
        result._meta = meta

    return result


def with_item(
    summary: str,
    item: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> CallToolResult:
    """
    Create a tool response containing a single item.

    Args:
        summary: Human-readable description (e.g., "Task T001")
        item: Structured item data
        meta: Hidden metadata for client applications (optional)

    Returns:
        CallToolResult with item data

    Example:
        >>> with_item(
        ...     "Task T001: Implement feature",
        ...     item={
        ...         "id": "T001",
        ...         "title": "Implement feature",
        ...         "status": "ready"
        ...     }
        ... )
    """
    result = CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structuredContent=item,
    )

    if meta is not None:
        result._meta = meta

    return result


def empty(
    summary: str = "No results",
    meta: dict[str, Any] | None = None,
) -> CallToolResult:
    """
    Create an empty tool response.

    Args:
        summary: Human-readable description
        meta: Hidden metadata for client applications (optional)

    Returns:
        CallToolResult with no structured data

    Example:
        >>> empty("No tasks found")
    """
    result = CallToolResult(
        content=[TextContent(type="text", text=summary)],
    )

    if meta is not None:
        result._meta = meta

    return result


def format_summary(
    action: str,
    subject: str,
    details: str | None = None,
) -> str:
    """
    Format a consistent human-readable summary for tool responses.

    Args:
        action: The action performed (e.g., "Created", "Found", "Updated")
        subject: The subject of the action (e.g., "task T001", "5 tasks")
        details: Optional additional details

    Returns:
        Formatted summary string

    Example:
        >>> format_summary("Created", "task T001", "with priority 1")
        'Created task T001 with priority 1'
    """
    if details:
        return f"{action} {subject} {details}"
    return f"{action} {subject}"
