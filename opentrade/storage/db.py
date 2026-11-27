"""Database connection and transaction management per docs/DATABASE.md.

Supports PostgreSQL (via DATABASE_URL + psycopg v3) and SQLite 3 (WAL + foreign keys).
"""

import os
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from opentrade.storage.postgres_compat import PostgresConnectionWrapper, is_postgres_url

try:
    import psycopg
except ImportError:  # pragma: no cover - optional until installed in prod
    psycopg = None  # type: ignore[assignment]


def _resolve_database_url() -> str | None:
    """Resolve DATABASE_URL from process environment or local .env file."""
    env_url = os.environ.get("DATABASE_URL")
    if env_url and env_url.strip():
        return env_url.strip()
    if Path(".env").is_file():
        file_url = dotenv_values(".env").get("DATABASE_URL")
        if file_url and str(file_url).strip():
            return str(file_url).strip()
    return None


def get_connection(
    db_path: str | Path | None = None,
    timeout: float = 30.0,
) -> Any:
    """Create a PostgreSQL (when DATABASE_URL is active) or SQLite connection."""
    target_url = str(db_path).strip() if db_path and is_postgres_url(db_path) else None
    if db_path is None:
        target_url = _resolve_database_url()

    if target_url and is_postgres_url(target_url):
        if psycopg is None:
            raise RuntimeError(
                "psycopg is required for PostgreSQL connections. Install 'psycopg[binary]'."
            )
        pg_conn = psycopg.connect(target_url, autocommit=True, connect_timeout=int(timeout))
        return PostgresConnectionWrapper(pg_conn)

    target_path = (
        Path(db_path)
        if db_path
        else Path(os.environ.get("OPENTRADE_DB_PATH") or "./data/opentrade.db")
    )
    if str(target_path) != ":memory:":
        target_path.parent.mkdir(parents=True, exist_ok=True)

    conn: sqlite3.Connection = sqlite3.connect(
        str(target_path),
        timeout=timeout,
        isolation_level=None,
    )
    conn.execute("PRAGMA foreign_keys = ON;")
    if str(target_path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def transaction(conn: Any) -> Generator[Any, Any, None]:
    """Context manager for executing statements inside a single transaction."""
    begin_stmt = "BEGIN;" if isinstance(conn, PostgresConnectionWrapper) else "BEGIN IMMEDIATE;"
    conn.execute(begin_stmt)
    cursor = conn.cursor()
    try:
        yield cursor
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise
    finally:
        cursor.close()
