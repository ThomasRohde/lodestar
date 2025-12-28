"""Add target_agent_id and correlation_id to events table.

Revision ID: 002
Revises: 001
Create Date: 2025-12-28

This migration adds fields to the events table to support MCP event streaming:
- target_agent_id: For tracking events targeted at specific agents (e.g., messages)
- correlation_id: For tracking related events across the system
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add target_agent_id and correlation_id columns to events table."""
    # Add target_agent_id column (nullable to support existing events)
    op.add_column("events", sa.Column("target_agent_id", sa.String(), nullable=True))

    # Add correlation_id column (nullable to support existing events)
    op.add_column("events", sa.Column("correlation_id", sa.String(), nullable=True))

    # Add index on correlation_id for efficient lookup of related events
    op.create_index("idx_events_correlation", "events", ["correlation_id"])


def downgrade() -> None:
    """Remove target_agent_id and correlation_id columns from events table."""
    op.drop_index("idx_events_correlation", table_name="events")
    op.drop_column("events", "correlation_id")
    op.drop_column("events", "target_agent_id")
