"""Database connection and transaction management per docs/DATABASE.md.

Engine: SQLite 3 with WAL mode and foreign keys enabled on every connection.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def get_connection(
    db_path: str | Path | None = None,
    timeout: float = 30.0,
) -> sqlite3.Connection:
    """Create a SQLite connection with foreign keys enabled and WAL journal mode.

    Args:
        db_path: Path to SQLite database file. Defaults to './data/opentrade.db'.
        timeout: SQLite lock timeout in seconds.

    Returns:
        sqlite3.Connection: Active database connection.
    """
    target_path = Path(db_path) if db_path else Path("./data/opentrade.db")

    # If it's not in-memory, ensure parent directory exists
    if str(target_path) != ":memory:":
        target_path.parent.mkdir(parents=True, exist_ok=True)

    # isolation_level=None enables autocommit mode so explicit BEGIN/COMMIT work cleanly
    conn: sqlite3.Connection = sqlite3.connect(
        str(target_path),
        timeout=timeout,
        isolation_level=None,
    )

    # Enable foreign keys on every connection
    conn.execute("PRAGMA foreign_keys = ON;")

    # Enable WAL mode for disk-backed databases
    if str(target_path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL;")

    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[sqlite3.Cursor, Any, None]:
    """Context manager for executing statements inside a single transaction.

    Rolls back automatically on exception and commits on success.
    """
    conn.execute("BEGIN IMMEDIATE;")
    cursor = conn.cursor()
    try:
        yield cursor
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise
    finally:
        cursor.close()
