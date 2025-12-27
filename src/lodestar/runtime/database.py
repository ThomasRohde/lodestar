"""SQLite runtime database management with WAL mode."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from lodestar.models.runtime import Agent, Lease, Message, MessageType
from lodestar.util.paths import get_runtime_db_path


class RuntimeDatabase:
    """SQLite database for runtime state with WAL mode for concurrency."""

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Path | None = None):
        """Initialize the runtime database.

        Args:
            db_path: Path to the database file. If None, uses default location.
        """
        self.db_path = db_path or get_runtime_db_path()
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        """Ensure database is created and migrated."""
        with self._connect() as conn:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")

            # Create schema
            self._create_schema(conn)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection."""
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        """Create database schema."""
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                display_name TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                capabilities TEXT DEFAULT '{}',
                session_meta TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS leases (
                lease_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
            );

            CREATE INDEX IF NOT EXISTS idx_leases_task_id ON leases(task_id);
            CREATE INDEX IF NOT EXISTS idx_leases_agent_id ON leases(agent_id);
            CREATE INDEX IF NOT EXISTS idx_leases_expires_at ON leases(expires_at);

            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                from_agent_id TEXT NOT NULL,
                to_type TEXT NOT NULL,
                to_id TEXT NOT NULL,
                text TEXT NOT NULL,
                meta TEXT DEFAULT '{}',
                FOREIGN KEY (from_agent_id) REFERENCES agents(agent_id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_type, to_id);
            CREATE INDEX IF NOT EXISTS idx_messages_from ON messages(from_agent_id);
            CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);

            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                agent_id TEXT,
                task_id TEXT,
                data TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
            """
        )

    # Agent operations

    def register_agent(self, agent: Agent) -> Agent:
        """Register a new agent."""
        import json

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agents (agent_id, display_name, created_at, last_seen_at,
                                   capabilities, session_meta)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    agent.agent_id,
                    agent.display_name,
                    agent.created_at.isoformat(),
                    agent.last_seen_at.isoformat(),
                    json.dumps(agent.capabilities),
                    json.dumps(agent.session_meta),
                ),
            )

            self._log_event(conn, "agent.join", agent.agent_id, None, {})

        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        """Get an agent by ID."""
        import json

        with self._connect() as conn:
            row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()

            if row is None:
                return None

            return Agent(
                agent_id=row["agent_id"],
                display_name=row["display_name"],
                created_at=datetime.fromisoformat(row["created_at"]),
                last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
                capabilities=json.loads(row["capabilities"]),
                session_meta=json.loads(row["session_meta"]),
            )

    def list_agents(self, active_only: bool = False) -> list[Agent]:
        """List all registered agents."""
        import json

        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM agents ORDER BY last_seen_at DESC").fetchall()

            agents = []
            for row in rows:
                agents.append(
                    Agent(
                        agent_id=row["agent_id"],
                        display_name=row["display_name"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
                        capabilities=json.loads(row["capabilities"]),
                        session_meta=json.loads(row["session_meta"]),
                    )
                )

            return agents

    def update_heartbeat(self, agent_id: str) -> bool:
        """Update an agent's heartbeat timestamp."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE agents SET last_seen_at = ? WHERE agent_id = ?
                """,
                (datetime.utcnow().isoformat(), agent_id),
            )
            return cursor.rowcount > 0

    # Lease operations

    def create_lease(self, lease: Lease) -> Lease | None:
        """Create a new lease atomically.

        Returns the lease if created, None if the task already has an active lease.
        """
        now = datetime.utcnow()

        with self._connect() as conn:
            # Check for existing active lease (atomic within transaction)
            existing = conn.execute(
                """
                SELECT lease_id FROM leases
                WHERE task_id = ? AND expires_at > ?
                """,
                (lease.task_id, now.isoformat()),
            ).fetchone()

            if existing:
                return None  # Task already claimed

            # Create the lease
            conn.execute(
                """
                INSERT INTO leases (lease_id, task_id, agent_id, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    lease.lease_id,
                    lease.task_id,
                    lease.agent_id,
                    lease.created_at.isoformat(),
                    lease.expires_at.isoformat(),
                ),
            )

            self._log_event(
                conn,
                "task.claim",
                lease.agent_id,
                lease.task_id,
                {"lease_id": lease.lease_id},
            )

            return lease

    def get_active_lease(self, task_id: str) -> Lease | None:
        """Get the active lease for a task, if any."""
        now = datetime.utcnow()

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM leases
                WHERE task_id = ? AND expires_at > ?
                ORDER BY expires_at DESC LIMIT 1
                """,
                (task_id, now.isoformat()),
            ).fetchone()

            if row is None:
                return None

            return Lease(
                lease_id=row["lease_id"],
                task_id=row["task_id"],
                agent_id=row["agent_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                expires_at=datetime.fromisoformat(row["expires_at"]),
            )

    def get_agent_leases(self, agent_id: str, active_only: bool = True) -> list[Lease]:
        """Get all leases for an agent."""
        now = datetime.utcnow()

        with self._connect() as conn:
            if active_only:
                rows = conn.execute(
                    """
                    SELECT * FROM leases
                    WHERE agent_id = ? AND expires_at > ?
                    ORDER BY expires_at DESC
                    """,
                    (agent_id, now.isoformat()),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM leases
                    WHERE agent_id = ?
                    ORDER BY expires_at DESC
                    """,
                    (agent_id,),
                ).fetchall()

            return [
                Lease(
                    lease_id=row["lease_id"],
                    task_id=row["task_id"],
                    agent_id=row["agent_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    expires_at=datetime.fromisoformat(row["expires_at"]),
                )
                for row in rows
            ]

    def renew_lease(self, lease_id: str, new_expires_at: datetime, agent_id: str) -> bool:
        """Renew a lease (only if owned by agent and still active)."""
        now = datetime.utcnow()

        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE leases
                SET expires_at = ?
                WHERE lease_id = ? AND agent_id = ? AND expires_at > ?
                """,
                (new_expires_at.isoformat(), lease_id, agent_id, now.isoformat()),
            )

            if cursor.rowcount > 0:
                # Get task_id for logging
                row = conn.execute(
                    "SELECT task_id FROM leases WHERE lease_id = ?", (lease_id,)
                ).fetchone()
                if row:
                    self._log_event(
                        conn,
                        "task.renew",
                        agent_id,
                        row["task_id"],
                        {"lease_id": lease_id},
                    )
                return True

            return False

    def release_lease(self, task_id: str, agent_id: str) -> bool:
        """Release a lease (set expires_at to now)."""
        now = datetime.utcnow()

        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE leases
                SET expires_at = ?
                WHERE task_id = ? AND agent_id = ? AND expires_at > ?
                """,
                (now.isoformat(), task_id, agent_id, now.isoformat()),
            )

            if cursor.rowcount > 0:
                self._log_event(conn, "task.release", agent_id, task_id, {})
                return True

            return False

    # Message operations

    def send_message(self, message: Message) -> Message:
        """Send a message."""
        import json

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (message_id, created_at, from_agent_id,
                                     to_type, to_id, text, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.created_at.isoformat(),
                    message.from_agent_id,
                    message.to_type.value,
                    message.to_id,
                    message.text,
                    json.dumps(message.meta),
                ),
            )

            self._log_event(
                conn,
                "message.send",
                message.from_agent_id,
                message.to_id if message.to_type == MessageType.TASK else None,
                {"to_type": message.to_type.value, "to_id": message.to_id},
            )

            return message

    def get_inbox(
        self, agent_id: str, since: datetime | None = None, limit: int = 50
    ) -> list[Message]:
        """Get messages for an agent."""
        import json

        with self._connect() as conn:
            if since:
                rows = conn.execute(
                    """
                    SELECT * FROM messages
                    WHERE to_type = 'agent' AND to_id = ? AND created_at > ?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (agent_id, since.isoformat(), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM messages
                    WHERE to_type = 'agent' AND to_id = ?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (agent_id, limit),
                ).fetchall()

            return [
                Message(
                    message_id=row["message_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    from_agent_id=row["from_agent_id"],
                    to_type=MessageType(row["to_type"]),
                    to_id=row["to_id"],
                    text=row["text"],
                    meta=json.loads(row["meta"]),
                )
                for row in rows
            ]

    def get_task_thread(
        self, task_id: str, since: datetime | None = None, limit: int = 50
    ) -> list[Message]:
        """Get messages for a task thread."""
        import json

        with self._connect() as conn:
            if since:
                rows = conn.execute(
                    """
                    SELECT * FROM messages
                    WHERE to_type = 'task' AND to_id = ? AND created_at > ?
                    ORDER BY created_at ASC LIMIT ?
                    """,
                    (task_id, since.isoformat(), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM messages
                    WHERE to_type = 'task' AND to_id = ?
                    ORDER BY created_at ASC LIMIT ?
                    """,
                    (task_id, limit),
                ).fetchall()

            return [
                Message(
                    message_id=row["message_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    from_agent_id=row["from_agent_id"],
                    to_type=MessageType(row["to_type"]),
                    to_id=row["to_id"],
                    text=row["text"],
                    meta=json.loads(row["meta"]),
                )
                for row in rows
            ]

    # Statistics

    def get_stats(self) -> dict[str, Any]:
        """Get runtime statistics."""
        now = datetime.utcnow()

        with self._connect() as conn:
            agent_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]

            active_leases = conn.execute(
                "SELECT COUNT(*) FROM leases WHERE expires_at > ?",
                (now.isoformat(),),
            ).fetchone()[0]

            total_messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

            return {
                "agents": agent_count,
                "active_leases": active_leases,
                "total_messages": total_messages,
            }

    def _log_event(
        self,
        conn: sqlite3.Connection,
        event_type: str,
        agent_id: str | None,
        task_id: str | None,
        data: dict[str, Any],
    ) -> None:
        """Log an event to the events table."""
        import json

        conn.execute(
            """
            INSERT INTO events (created_at, event_type, agent_id, task_id, data)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                datetime.utcnow().isoformat(),
                event_type,
                agent_id,
                task_id,
                json.dumps(data),
            ),
        )
