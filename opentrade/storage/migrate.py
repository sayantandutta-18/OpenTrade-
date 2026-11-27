"""Database migration runner per docs/DATABASE.md.

Applies numbered SQL files in order. Each migration runs in one transaction.
A failed migration rolls back and stops execution.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opentrade.storage.db import get_connection, transaction

DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def get_applied_versions(conn: Any) -> set[int]:
    """Retrieve the set of already applied migration version numbers."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            """)
        rows = cursor.execute("SELECT version FROM schema_migrations;").fetchall()
        return {int(row[0]) for row in rows}
    finally:
        cursor.close()


def parse_version(file_path: Path) -> int:
    """Extract numeric version prefix from a migration filename (e.g. 0001_init.sql -> 1)."""
    prefix = file_path.name.split("_")[0]
    try:
        return int(prefix)
    except ValueError as exc:
        raise ValueError(
            f"Invalid migration filename format: {file_path.name}. Must start with number."
        ) from exc


def split_sql_statements(sql: str) -> list[str]:
    """Split a SQL script into individual statements by semicolon, ignoring comments."""
    lines: list[str] = []
    for line in sql.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("--"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    return [stmt.strip() for stmt in cleaned.split(";") if stmt.strip()]


def run_migrations(
    db_path: str | Path | None = None,
    migrations_dir: str | Path | None = None,
) -> int:
    """Run all pending SQL migrations against the database.

    Args:
        db_path: Path to the SQLite database file.
        migrations_dir: Directory containing numbered .sql migration files.

    Returns:
        int: Number of migrations successfully applied in this run.

    Raises:
        Exception: If any migration fails, after rolling back the transaction.
    """
    target_dir = Path(migrations_dir) if migrations_dir else DEFAULT_MIGRATIONS_DIR
    conn = get_connection(db_path)

    try:
        applied_versions = get_applied_versions(conn)

        migration_files = sorted(
            [f for f in target_dir.glob("*.sql") if f.is_file()],
            key=parse_version,
        )

        applied_count = 0

        for mig_file in migration_files:
            version = parse_version(mig_file)
            if version in applied_versions:
                continue

            sql_content = mig_file.read_text(encoding="utf-8").strip()
            if not sql_content:
                continue

            now_iso = datetime.now(UTC).isoformat()
            statements = split_sql_statements(sql_content)

            # Execute migration and record in schema_migrations within one transaction
            with transaction(conn) as cursor:
                for stmt in statements:
                    cursor.execute(stmt)
                cursor.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?);",
                    (version, now_iso),
                )

            applied_count += 1

        return applied_count
    finally:
        conn.close()


if __name__ == "__main__":
    db_arg = sys.argv[1] if len(sys.argv) > 1 else None
    count = run_migrations(db_arg)
    print(f"Applied {count} migration(s).")
