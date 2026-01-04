"""Convert messages to task-only messaging with read tracking.

Revision ID: 003
Revises: 002
Create Date: 2026-01-03

This migration restructures the messages table to only support task-targeted messages:
- Removes to_type and to_id columns (agent messaging deprecated)
- Adds task_id column (all messages are task-targeted)
- Replaces read_at with read_by JSON array for multi-agent read tracking
- Updates indexes for new schema
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Convert messages table to task-only messaging."""
    # Create new messages table with task-only schema
    op.create_table(
        "messages_new",
        sa.Column("message_id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("from_agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("read_by", sa.JSON(), nullable=False, server_default="[]"),
    )

    # Migrate task messages from old table (drop agent messages)
    op.execute("""
        INSERT INTO messages_new (message_id, created_at, from_agent_id, task_id, text, meta, read_by)
        SELECT
            message_id,
            created_at,
            from_agent_id,
            to_id as task_id,
            text,
            COALESCE(meta, '{}'),
            '[]' as read_by
        FROM messages
        WHERE to_type = 'task'
    """)

    # Drop old table
    op.drop_index("idx_messages_to", table_name="messages")
    op.drop_index("idx_messages_from", table_name="messages")
    op.drop_index("idx_messages_created", table_name="messages")
    op.drop_table("messages")

    # Rename new table
    op.rename_table("messages_new", "messages")

    # Create indexes on new schema
    op.create_index("idx_messages_task", "messages", ["task_id"])
    op.create_index("idx_messages_from", "messages", ["from_agent_id"])
    op.create_index("idx_messages_created", "messages", ["created_at"])


def downgrade() -> None:
    """Revert to old messages schema (WARNING: agent messages cannot be restored)."""
    # Create old messages table structure
    op.create_table(
        "messages_old",
        sa.Column("message_id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("from_agent_id", sa.String(), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("to_type", sa.String(), nullable=False),
        sa.Column("to_id", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("read_at", sa.String(), nullable=True),
    )

    # Migrate task messages back (cannot restore agent messages or read tracking)
    op.execute("""
        INSERT INTO messages_old (message_id, created_at, from_agent_id, to_type, to_id, text, meta, read_at)
        SELECT
            message_id,
            created_at,
            from_agent_id,
            'task' as to_type,
            task_id as to_id,
            text,
            COALESCE(meta, '{}'),
            NULL as read_at
        FROM messages
    """)

    # Drop new table
    op.drop_index("idx_messages_task", table_name="messages")
    op.drop_index("idx_messages_from", table_name="messages")
    op.drop_index("idx_messages_created", table_name="messages")
    op.drop_table("messages")

    # Rename old table back
    op.rename_table("messages_old", "messages")

    # Restore old indexes
    op.create_index("idx_messages_to", "messages", ["to_type", "to_id"])
    op.create_index("idx_messages_from", "messages", ["from_agent_id"])
    op.create_index("idx_messages_created", "messages", ["created_at"])
