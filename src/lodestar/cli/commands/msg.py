"""lodestar msg commands - Task messaging."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import typer

from lodestar.models.envelope import Envelope
from lodestar.models.runtime import Message
from lodestar.runtime.database import RuntimeDatabase
from lodestar.util.output import console, print_json
from lodestar.util.paths import find_lodestar_root, get_runtime_db_path

app = typer.Typer(
    help="Task messaging commands.",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def msg_callback(ctx: typer.Context) -> None:
    """Task messaging.

    Use these commands to communicate via task threads and leave context for handoffs.
    All messages are task-targeted - there is no agent-to-agent messaging.
    """
    if ctx.invoked_subcommand is None:
        # Show helpful workflow instead of error
        console.print()
        console.print("[bold]Task Message Commands[/bold]")
        console.print()
        console.print("[info]Sending messages:[/info]")
        console.print(
            "  [command]lodestar msg send --task <id> --from <agent-id> --text '...'[/command]"
        )
        console.print(
            "      Leave context on a task thread (visible to all agents working on the task)"
        )
        console.print()
        console.print("[info]Reading messages:[/info]")
        console.print("  [command]lodestar msg thread <task-id>[/command]")
        console.print("      Read all messages in a task thread")
        console.print()
        console.print("  [command]lodestar msg mark-read --task <id> --agent <id>[/command]")
        console.print("      Mark task messages as read")
        console.print()
        console.print("  [command]lodestar msg search --keyword <term>[/command]")
        console.print("      Search messages across all tasks")
        console.print()
        console.print("[info]Examples:[/info]")
        console.print("  lodestar msg send --task F001 --from A123 --text 'Blocked on X'")
        console.print("  lodestar msg thread F001")
        console.print("  lodestar msg mark-read --task F001 --agent A123")
        console.print("  lodestar msg search --keyword 'bug' --task F001")
        console.print()


@app.command(name="send")
def msg_send(
    task_id: str = typer.Option(
        ...,
        "--task",
        "-t",
        help="(REQUIRED) Task ID to send message to.",
    ),
    text: str = typer.Option(
        ...,
        "--text",
        "-m",
        help="(REQUIRED) Message text.",
    ),
    from_agent: str = typer.Option(
        ...,
        "--from",
        "-f",
        help="(REQUIRED) Your agent ID. Get it from 'lodestar agent join'.",
    ),
    subject: str | None = typer.Option(
        None,
        "--subject",
        "-s",
        help="Optional message subject (stored in meta).",
    ),
    severity: str | None = typer.Option(
        None,
        "--severity",
        help="Optional severity level (stored in meta): info, warning, handoff, blocker.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Show what this command does.",
    ),
) -> None:
    """Send a message to a task thread.

    Task messages are visible to all agents working on the task.
    Use for handoffs, status updates, questions, or leaving context.

    Examples:
        lodestar msg send --task F001 --from A123 --text 'Blocked on API key'
        lodestar msg send --task F001 --from A123 --text 'Done' --subject 'Ready for review'
    """
    if explain:
        _show_explain_send(json_output)
        return

    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    # Create and send message
    db = RuntimeDatabase(get_runtime_db_path(root))

    meta: dict[str, Any] = {}
    if subject:
        meta["subject"] = subject
    if severity:
        meta["severity"] = severity

    message = Message(
        from_agent_id=from_agent,
        task_id=task_id,
        text=text,
        meta=meta,
    )
    db.send_message(message)

    result = {
        "message_id": message.message_id,
        "sent_at": message.created_at.isoformat(),
        "task_id": task_id,
        "from_agent_id": from_agent,
    }

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print(f"[success]Message sent[/success] to task [bold]{task_id}[/bold]")
        console.print(f"  Message ID: {message.message_id}")


@app.command(name="thread")
def msg_thread(
    task_id: str = typer.Argument(..., help="Task ID to view thread for."),
    since: str | None = typer.Option(
        None,
        "--since",
        "-s",
        help="Filter messages created after this timestamp (ISO format).",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Maximum messages to return.",
    ),
    unread_only: bool = typer.Option(
        False,
        "--unread",
        help="Show only unread messages for --agent.",
    ),
    agent_id: str | None = typer.Option(
        None,
        "--agent",
        "-a",
        help="Agent ID for filtering unread messages.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Show what this command does.",
    ),
) -> None:
    """Read messages in a task thread.

    Shows all messages for a task (use --unread --agent to see only unread).

    Examples:
        lodestar msg thread F001
        lodestar msg thread F001 --unread --agent A123
        lodestar msg thread F001 --since 2026-01-01T00:00:00
    """
    if explain:
        _show_explain_thread(json_output)
        return

    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    # Strip 'task:' prefix if present for consistency
    if task_id.startswith("task:"):
        task_id = task_id[5:]

    runtime_path = get_runtime_db_path(root)
    if not runtime_path.exists():
        messages = []
    else:
        db = RuntimeDatabase(runtime_path)

        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                if json_output:
                    print_json(Envelope.error(f"Invalid timestamp: {since}").model_dump())
                else:
                    console.print(f"[error]Invalid timestamp: {since}[/error]")
                raise typer.Exit(1)

        # Get messages (optionally filtered for unread)
        if unread_only and agent_id:
            messages = db.get_task_unread_messages(task_id, agent_id, limit=limit)
            # Still apply since filter if provided
            if since_dt:
                messages = [m for m in messages if m.created_at > since_dt]
        else:
            messages = db.get_task_thread(
                task_id, since=since_dt, limit=limit, unread_by=agent_id if unread_only else None
            )

    result = {
        "task_id": task_id,
        "messages": [
            {
                "message_id": m.message_id,
                "from_agent_id": m.from_agent_id,
                "text": m.text,
                "created_at": m.created_at.isoformat(),
                "read_by": m.read_by,
                "meta": m.meta,
            }
            for m in messages
        ],
        "count": len(messages),
        "cursor": messages[-1].created_at.isoformat() if messages else None,
    }

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print()
        unread_text = " (unread)" if unread_only else ""
        console.print(f"[bold]Thread for {task_id}{unread_text}[/bold]")
        console.print()
        if not messages:
            console.print("[muted]No messages in thread.[/muted]")
        else:
            for msg in messages:
                console.print(f"  [muted]{msg.created_at.isoformat()}[/muted]")
                read_text = f" [muted](read by {len(msg.read_by)})[/muted]" if msg.read_by else ""
                console.print(f"  [agent_id]{msg.from_agent_id}[/agent_id]{read_text}: {msg.text}")
                if msg.meta:
                    console.print(f"  [dim]Meta: {msg.meta}[/dim]")
                console.print()
        console.print()


@app.command(name="search")
def msg_search(
    keyword: str | None = typer.Option(
        None,
        "--keyword",
        "-k",
        help="Search keyword to match in message text (case-insensitive).",
    ),
    task_id: str | None = typer.Option(
        None,
        "--task",
        "-t",
        help="Filter by task ID.",
    ),
    from_agent: str | None = typer.Option(
        None,
        "--from",
        "-f",
        help="Filter by sender agent ID.",
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        "-s",
        help="Filter messages created after this timestamp (ISO format).",
    ),
    until: str | None = typer.Option(
        None,
        "--until",
        "-u",
        help="Filter messages created before this timestamp (ISO format).",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Maximum messages to return.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Show what this command does.",
    ),
) -> None:
    """Search messages with filters.

    Search across all task messages with optional keyword matching and filters.
    At least one filter must be provided.

    Examples:
        lodestar msg search --keyword 'bug'
        lodestar msg search --task F001
        lodestar msg search --from A123 --since 2025-01-01T00:00:00
        lodestar msg search --keyword 'error' --until 2025-12-31T23:59:59
    """
    if explain:
        _show_explain_search(json_output)
        return

    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    # Validate at least one filter is provided
    if not any([keyword, task_id, from_agent, since, until]):
        if json_output:
            print_json(
                Envelope.error(
                    "At least one filter is required (--keyword, --task, --from, --since, or --until)"
                ).model_dump()
            )
        else:
            console.print("[error]At least one filter is required[/error]")
            console.print("Use --keyword, --task, --from, --since, or --until")
        raise typer.Exit(1)

    runtime_path = get_runtime_db_path(root)
    if not runtime_path.exists():
        messages = []
    else:
        db = RuntimeDatabase(runtime_path)

        # Parse timestamps
        since_dt = None
        until_dt = None

        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                if json_output:
                    print_json(Envelope.error(f"Invalid since timestamp: {since}").model_dump())
                else:
                    console.print(f"[error]Invalid since timestamp: {since}[/error]")
                raise typer.Exit(1)

        if until:
            try:
                until_dt = datetime.fromisoformat(until)
            except ValueError:
                if json_output:
                    print_json(Envelope.error(f"Invalid until timestamp: {until}").model_dump())
                else:
                    console.print(f"[error]Invalid until timestamp: {until}[/error]")
                raise typer.Exit(1)

        messages = db.search_messages(
            keyword=keyword,
            task_id=task_id,
            from_agent_id=from_agent,
            since=since_dt,
            until=until_dt,
            limit=limit,
        )

    result = {
        "messages": [
            {
                "message_id": m.message_id,
                "from_agent_id": m.from_agent_id,
                "task_id": m.task_id,
                "text": m.text,
                "created_at": m.created_at.isoformat(),
                "read_by": m.read_by,
                "meta": m.meta,
            }
            for m in messages
        ],
        "count": len(messages),
        "filters": {
            "keyword": keyword,
            "task_id": task_id,
            "from_agent_id": from_agent,
            "since": since,
            "until": until,
        },
    }

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print()
        if not messages:
            console.print("[muted]No messages found.[/muted]")
        else:
            console.print(f"[bold]Search Results ({len(messages)} messages)[/bold]")
            console.print()
            for msg in messages:
                console.print(f"  [muted]{msg.created_at.isoformat()}[/muted]")
                console.print(f"  From: [agent_id]{msg.from_agent_id}[/agent_id]")
                console.print(f"  Task: [bold]{msg.task_id}[/bold]")
                read_text = f" [muted](read by {len(msg.read_by)})[/muted]" if msg.read_by else ""
                console.print(f"  {msg.text}{read_text}")
                if msg.meta:
                    console.print(f"  [dim]Meta: {msg.meta}[/dim]")
                console.print()
        console.print()


@app.command(name="mark-read")
def msg_mark_read(
    task_id: str = typer.Option(
        ...,
        "--task",
        "-t",
        help="(REQUIRED) Task ID whose messages to mark as read.",
    ),
    agent_id: str = typer.Option(
        ...,
        "--agent",
        "-a",
        help="(REQUIRED) Agent ID marking messages as read.",
    ),
    message_ids: list[str] | None = typer.Option(
        None,
        "--message-id",
        "-m",
        help="Specific message ID(s) to mark as read. If not provided, marks all task messages.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Show what this command does.",
    ),
) -> None:
    """Mark task messages as read.

    Mark specific messages or all messages in a task as read by an agent.
    This updates the read_by array for the messages.

    Examples:
        lodestar msg mark-read --task F001 --agent A123
        lodestar msg mark-read --task F001 --agent A123 --message-id M001 --message-id M002
    """
    if explain:
        _show_explain_mark_read(json_output)
        return

    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    runtime_path = get_runtime_db_path(root)
    if not runtime_path.exists():
        if json_output:
            print_json(Envelope.error("Runtime database does not exist").model_dump())
        else:
            console.print("[error]Runtime database does not exist[/error]")
        raise typer.Exit(1)

    db = RuntimeDatabase(runtime_path)

    # Mark messages as read
    updated_count = db.mark_task_messages_read(
        task_id=task_id,
        agent_id=agent_id,
        message_ids=message_ids if message_ids else None,
    )

    result = {
        "task_id": task_id,
        "agent_id": agent_id,
        "messages_marked": updated_count,
    }

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print(
            f"[success]Marked {updated_count} message(s) as read[/success] "
            f"in task [bold]{task_id}[/bold]"
        )


def _show_explain_send(json_output: bool) -> None:
    explanation = {
        "command": "lodestar msg send",
        "purpose": "Send a message to a task thread.",
        "examples": [
            "lodestar msg send --task F001 --from A123 --text 'Blocked on X'",
            "lodestar msg send --task F001 --from A123 --text 'Done' --subject 'Ready for review'",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar msg send[/info]\n")
        console.print("Send a message to a task thread.\n")


def _show_explain_thread(json_output: bool) -> None:
    explanation = {
        "command": "lodestar msg thread",
        "purpose": "Read messages in a task thread.",
        "examples": [
            "lodestar msg thread F001",
            "lodestar msg thread F001 --unread --agent A123",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar msg thread[/info]\n")
        console.print("Read messages in a task thread.\n")


def _show_explain_search(json_output: bool) -> None:
    explanation = {
        "command": "lodestar msg search",
        "purpose": "Search messages with filters.",
        "examples": [
            "lodestar msg search --keyword 'bug'",
            "lodestar msg search --task F001",
            "lodestar msg search --from A123 --since 2025-01-01T00:00:00",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar msg search[/info]\n")
        console.print("Search messages with filters.\n")


def _show_explain_mark_read(json_output: bool) -> None:
    explanation = {
        "command": "lodestar msg mark-read",
        "purpose": "Mark task messages as read by an agent.",
        "examples": [
            "lodestar msg mark-read --task F001 --agent A123",
            "lodestar msg mark-read --task F001 --agent A123 --message-id M001",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar msg mark-read[/info]\n")
        console.print("Mark task messages as read by an agent.\n")
