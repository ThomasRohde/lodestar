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

    SCHEMA_VERSION = 3

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
            # Run migrations
            self._run_migrations(conn)

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
                role TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                capabilities TEXT DEFAULT '[]',
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

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        """Run database migrations."""
        # Get current schema version
        result = conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        current_version = result[0] if result else 0

        # Migration 1 -> 2: Add read_at column to messages table
        if current_version < 2:
            # Check if column already exists (for safety)
            cursor = conn.execute("PRAGMA table_info(messages)")
            columns = [row[1] for row in cursor.fetchall()]

            if "read_at" not in columns:
                conn.execute("ALTER TABLE messages ADD COLUMN read_at TEXT DEFAULT NULL")

            # Update schema version
            conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (2,))
            current_version = 2

        # Migration 2 -> 3: Add role column to agents table
        if current_version < 3:
            # Check if column already exists (for safety)
            cursor = conn.execute("PRAGMA table_info(agents)")
            columns = [row[1] for row in cursor.fetchall()]

            if "role" not in columns:
                conn.execute("ALTER TABLE agents ADD COLUMN role TEXT DEFAULT ''")

            # Update schema version
            conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (3,))

    # Agent operations

    def register_agent(self, agent: Agent) -> Agent:
        """Register a new agent."""
        import json

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agents (agent_id, display_name, role, created_at, last_seen_at,
                                   capabilities, session_meta)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent.agent_id,
                    agent.display_name,
                    agent.role,
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

            # Handle backward compatibility: old agents have capabilities as dict
            capabilities_raw = json.loads(row["capabilities"])
            capabilities = capabilities_raw if isinstance(capabilities_raw, list) else []

            return Agent(
                agent_id=row["agent_id"],
                display_name=row["display_name"],
                role=row["role"] or "",
                created_at=datetime.fromisoformat(row["created_at"]),
                last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
                capabilities=capabilities,
                session_meta=json.loads(row["session_meta"]),
            )

    def list_agents(self, active_only: bool = False) -> list[Agent]:
        """List all registered agents."""
        import json

        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM agents ORDER BY last_seen_at DESC").fetchall()

            agents = []
            for row in rows:
                # Handle backward compatibility: old agents have capabilities as dict
                capabilities_raw = json.loads(row["capabilities"])
                capabilities = capabilities_raw if isinstance(capabilities_raw, list) else []

                agents.append(
                    Agent(
                        agent_id=row["agent_id"],
                        display_name=row["display_name"],
                        role=row["role"] or "",
                        created_at=datetime.fromisoformat(row["created_at"]),
                        last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
                        capabilities=capabilities,
                        session_meta=json.loads(row["session_meta"]),
                    )
                )

            return agents

    def find_agents_by_capability(self, capability: str) -> list[Agent]:
        """Find agents that have a specific capability.

        Args:
            capability: The capability name to search for.

        Returns:
            List of agents that have the specified capability.
        """
        import json

        with self._connect() as conn:
            # Use JSON functions to search within the capabilities array
            # SQLite's json_each can expand a JSON array into rows
            rows = conn.execute(
                """
                SELECT DISTINCT a.* FROM agents a, json_each(a.capabilities) AS cap
                WHERE cap.value = ?
                ORDER BY a.last_seen_at DESC
                """,
                (capability,),
            ).fetchall()

            agents = []
            for row in rows:
                # Handle backward compatibility: old agents have capabilities as dict
                capabilities_raw = json.loads(row["capabilities"])
                capabilities = capabilities_raw if isinstance(capabilities_raw, list) else []

                agents.append(
                    Agent(
                        agent_id=row["agent_id"],
                        display_name=row["display_name"],
                        role=row["role"] or "",
                        created_at=datetime.fromisoformat(row["created_at"]),
                        last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
                        capabilities=capabilities,
                        session_meta=json.loads(row["session_meta"]),
                    )
                )

            return agents

    def find_agents_by_role(self, role: str) -> list[Agent]:
        """Find agents that have a specific role.

        Args:
            role: The role to search for.

        Returns:
            List of agents with the specified role.
        """
        import json

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM agents WHERE role = ?
                ORDER BY last_seen_at DESC
                """,
                (role,),
            ).fetchall()

            agents = []
            for row in rows:
                # Handle backward compatibility: old agents have capabilities as dict
                capabilities_raw = json.loads(row["capabilities"])
                capabilities = capabilities_raw if isinstance(capabilities_raw, list) else []

                agents.append(
                    Agent(
                        agent_id=row["agent_id"],
                        display_name=row["display_name"],
                        role=row["role"] or "",
                        created_at=datetime.fromisoformat(row["created_at"]),
                        last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
                        capabilities=capabilities,
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
        self,
        agent_id: str,
        since: datetime | None = None,
        until: datetime | None = None,
        from_agent_id: str | None = None,
        limit: int = 50,
        unread_only: bool = False,
        mark_as_read: bool = False,
    ) -> list[Message]:
        """Get messages for an agent.

        Args:
            agent_id: The agent whose inbox to retrieve
            since: Filter messages created after this time
            until: Filter messages created before this time
            from_agent_id: Filter by sender agent ID
            limit: Maximum number of messages to return
            unread_only: If True, only return unread messages (read_at IS NULL)
            mark_as_read: If True, mark returned messages as read

        Returns:
            List of messages matching the criteria
        """
        import json

        # Build query dynamically based on filters
        conditions = ["to_type = 'agent'", "to_id = ?"]
        params = [agent_id]

        if since:
            conditions.append("created_at > ?")
            params.append(since.isoformat())

        if until:
            conditions.append("created_at < ?")
            params.append(until.isoformat())

        if from_agent_id:
            conditions.append("from_agent_id = ?")
            params.append(from_agent_id)

        if unread_only:
            conditions.append("read_at IS NULL")

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT * FROM messages
            WHERE {where_clause}
            ORDER BY created_at DESC LIMIT ?
        """
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

            messages = [
                Message(
                    message_id=row["message_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    from_agent_id=row["from_agent_id"],
                    to_type=MessageType(row["to_type"]),
                    to_id=row["to_id"],
                    text=row["text"],
                    meta=json.loads(row["meta"]),
                    read_at=datetime.fromisoformat(row["read_at"]) if row["read_at"] else None,
                )
                for row in rows
            ]

            # Mark messages as read if requested
            if mark_as_read and messages:
                now = datetime.utcnow()
                message_ids = [msg.message_id for msg in messages]
                placeholders = ",".join("?" * len(message_ids))
                conn.execute(
                    f"UPDATE messages SET read_at = ? WHERE message_id IN ({placeholders})",
                    [now.isoformat()] + message_ids,
                )
                # Update the messages in-memory to reflect the read status
                for msg in messages:
                    if msg.read_at is None:
                        msg.read_at = now

            return messages

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
                    read_at=datetime.fromisoformat(row["read_at"]) if row["read_at"] else None,
                )
                for row in rows
            ]

    def get_task_message_count(self, task_id: str) -> int:
        """Get the count of messages in a task thread."""
        with self._connect() as conn:
            count = conn.execute(
                """
                SELECT COUNT(*) FROM messages
                WHERE to_type = 'task' AND to_id = ?
                """,
                (task_id,),
            ).fetchone()[0]
            return count

    def get_task_message_agents(self, task_id: str) -> list[str]:
        """Get unique agent IDs who have sent messages about a task."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT from_agent_id FROM messages
                WHERE to_type = 'task' AND to_id = ?
                ORDER BY from_agent_id
                """,
                (task_id,),
            ).fetchall()
            return [row[0] for row in rows]

    def search_messages(
        self,
        keyword: str | None = None,
        from_agent_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[Message]:
        """Search messages with optional filters.

        Args:
            keyword: Search term to match in message text (case-insensitive)
            from_agent_id: Filter by sender agent ID
            since: Filter messages created after this time
            until: Filter messages created before this time
            limit: Maximum number of messages to return

        Returns:
            List of messages matching the search criteria
        """
        import json

        # Build query dynamically based on filters
        conditions = []
        params = []

        if keyword:
            conditions.append("text LIKE ?")
            params.append(f"%{keyword}%")

        if from_agent_id:
            conditions.append("from_agent_id = ?")
            params.append(from_agent_id)

        if since:
            conditions.append("created_at > ?")
            params.append(since.isoformat())

        if until:
            conditions.append("created_at < ?")
            params.append(until.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"""
            SELECT * FROM messages
            WHERE {where_clause}
            ORDER BY created_at DESC LIMIT ?
        """
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

            return [
                Message(
                    message_id=row["message_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    from_agent_id=row["from_agent_id"],
                    to_type=MessageType(row["to_type"]),
                    to_id=row["to_id"],
                    text=row["text"],
                    meta=json.loads(row["meta"]),
                    read_at=datetime.fromisoformat(row["read_at"]) if row["read_at"] else None,
                )
                for row in rows
            ]

    def get_inbox_count(self, agent_id: str, since: datetime | None = None) -> int:
        """Get count of messages in inbox."""
        with self._connect() as conn:
            if since:
                result = conn.execute(
                    """
                    SELECT COUNT(*) FROM messages
                    WHERE to_type = 'agent' AND to_id = ? AND created_at > ?
                    """,
                    (agent_id, since.isoformat()),
                ).fetchone()
            else:
                result = conn.execute(
                    """
                    SELECT COUNT(*) FROM messages
                    WHERE to_type = 'agent' AND to_id = ?
                    """,
                    (agent_id,),
                ).fetchone()
            return result[0] if result else 0

    def wait_for_message(
        self, agent_id: str, timeout_seconds: float | None = None, since: datetime | None = None
    ) -> bool:
        """Wait for a new message to arrive.

        Returns True if a message was received, False if timeout occurred.
        Uses polling with exponential backoff to check for new messages.
        """
        import time

        # Check if there are already messages
        if self.get_inbox_count(agent_id, since=since) > 0:
            return True

        # Poll with exponential backoff
        start_time = time.time()
        sleep_time = 0.1  # Start with 100ms
        max_sleep = 2.0  # Cap at 2 seconds

        while True:
            # Check for timeout
            if timeout_seconds is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    return False

            # Sleep before next check
            time.sleep(sleep_time)

            # Check for new messages
            if self.get_inbox_count(agent_id, since=since) > 0:
                return True

            # Increase sleep time with exponential backoff
            sleep_time = min(sleep_time * 1.5, max_sleep)

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

    def get_agent_message_counts(self) -> dict[str, int]:
        """Get message count per agent.

        Returns a dictionary mapping agent_id to message count.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT to_id, COUNT(*) as count
                FROM messages
                WHERE to_type = 'agent'
                GROUP BY to_id
                """
            ).fetchall()

            return {row[0]: row[1] for row in rows}

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
