"""Initial schema for lodestar runtime database.

Revision ID: 001
Revises:
Create Date: 2024-01-01

This creates the same schema as the original raw SQLite implementation,
matching schema version 3 from the previous migration system.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Schema version table (for compatibility tracking)
    op.create_table(
        "schema_version",
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("version"),
    )

    # Agents table
    op.create_table(
        "agents",
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), server_default="", nullable=True),
        sa.Column("role", sa.String(), server_default="", nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("last_seen_at", sa.String(), nullable=False),
        sa.Column("capabilities", sa.Text(), server_default="[]", nullable=True),
        sa.Column("session_meta", sa.Text(), server_default="{}", nullable=True),
        sa.PrimaryKeyConstraint("agent_id"),
    )

    # Leases table
    op.create_table(
        "leases",
        sa.Column("lease_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("expires_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("lease_id"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.agent_id"]),
    )
    op.create_index("idx_leases_task_id", "leases", ["task_id"])
    op.create_index("idx_leases_agent_id", "leases", ["agent_id"])
    op.create_index("idx_leases_expires_at", "leases", ["expires_at"])

    # Messages table
    op.create_table(
        "messages",
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("from_agent_id", sa.String(), nullable=False),
        sa.Column("to_type", sa.String(), nullable=False),
        sa.Column("to_id", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("meta", sa.Text(), server_default="{}", nullable=True),
        sa.Column("read_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("message_id"),
        sa.ForeignKeyConstraint(["from_agent_id"], ["agents.agent_id"]),
    )
    op.create_index("idx_messages_to", "messages", ["to_type", "to_id"])
    op.create_index("idx_messages_from", "messages", ["from_agent_id"])
    op.create_index("idx_messages_created", "messages", ["created_at"])

    # Events table (audit log)
    op.create_table(
        "events",
        sa.Column("event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=True),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("data", sa.Text(), server_default="{}", nullable=True),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("idx_events_created", "events", ["created_at"])
    op.create_index("idx_events_type", "events", ["event_type"])


def downgrade() -> None:
    op.drop_index("idx_events_type", table_name="events")
    op.drop_index("idx_events_created", table_name="events")
    op.drop_table("events")

    op.drop_index("idx_messages_created", table_name="messages")
    op.drop_index("idx_messages_from", table_name="messages")
    op.drop_index("idx_messages_to", table_name="messages")
    op.drop_table("messages")

    op.drop_index("idx_leases_expires_at", table_name="leases")
    op.drop_index("idx_leases_agent_id", table_name="leases")
    op.drop_index("idx_leases_task_id", table_name="leases")
    op.drop_table("leases")

    op.drop_table("agents")
    op.drop_table("schema_version")
