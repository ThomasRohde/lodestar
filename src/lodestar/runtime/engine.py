"""SQLAlchemy engine and session management."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool


def _enable_wal_mode(dbapi_connection: object, connection_record: object) -> None:
    """Enable WAL mode and set busy timeout on connect.

    WAL (Write-Ahead Logging) mode allows concurrent reads and writes,
    which is essential for a CLI tool that may have multiple processes.
    """
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def create_runtime_engine(db_path: Path) -> Engine:
    """Create SQLAlchemy engine with WAL mode for concurrent access.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        SQLAlchemy Engine configured for the runtime database.
    """
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        # Disable connection pooling for CLI tool
        # NullPool ensures connections are closed immediately after use
        poolclass=NullPool,
    )

    # Register event listener for WAL mode
    event.listen(engine, "connect", _enable_wal_mode)

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to the engine.

    Args:
        engine: SQLAlchemy Engine to bind sessions to.

    Returns:
        A sessionmaker factory for creating sessions.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def get_session(session_factory: sessionmaker[Session]) -> Generator[Session]:
    """Get a session with automatic commit/rollback.

    This context manager provides the same transaction semantics as the
    original _connect() method: auto-commit on success, auto-rollback on
    exception, and always close the session.

    Args:
        session_factory: The sessionmaker to create sessions from.

    Yields:
        A SQLAlchemy Session.
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
