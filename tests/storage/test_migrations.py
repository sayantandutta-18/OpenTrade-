"""Tests for database connection and migration runner per docs/DATABASE.md."""

import sqlite3
from pathlib import Path

import pytest

from opentrade.storage.db import get_connection
from opentrade.storage.migrate import run_migrations


def test_wal_mode_and_foreign_keys_enabled(tmp_path: Path) -> None:
    """migration test: Verify WAL mode and foreign keys are enabled on every connection."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path)

    conn = get_connection(db_path)
    try:
        fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk == 1, "Foreign keys must be enabled on every connection"

        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert journal_mode.lower() == "wal", f"Journal mode must be WAL, got {journal_mode}"
    finally:
        conn.close()


def test_schema_migrations_table_exists(tmp_path: Path) -> None:
    """migration test: Verify schema_migrations table tracks applied migrations."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path)

    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT version, applied_at FROM schema_migrations ORDER BY version;"
        ).fetchall()
        assert len(rows) >= 1
        assert rows[0][0] == 1  # 0001_init.sql
    finally:
        conn.close()


def test_0001_tables_and_columns_exist(tmp_path: Path) -> None:
    """migration test: Verify users, sessions, and auth_tokens have columns per DATABASE.md."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path)

    conn = get_connection(db_path)
    try:
        # Check users table
        user_cols = {
            row[1]: {"type": row[2].upper(), "notnull": row[3], "pk": row[5]}
            for row in conn.execute("PRAGMA table_info(users);").fetchall()
        }
        expected_user_cols = {
            "id",
            "name",
            "email",
            "password_hash",
            "email_verified_at",
            "failed_logins",
            "locked_until",
            "created_at",
            "updated_at",
        }
        assert expected_user_cols.issubset(user_cols.keys())
        assert user_cols["id"]["pk"] == 1
        assert user_cols["name"]["notnull"] == 1
        assert user_cols["email"]["notnull"] == 1
        assert user_cols["password_hash"]["notnull"] == 1
        assert user_cols["email_verified_at"]["notnull"] == 0
        assert user_cols["failed_logins"]["notnull"] == 1

        # Check sessions table
        session_cols = {
            row[1]: {"type": row[2].upper(), "notnull": row[3], "pk": row[5]}
            for row in conn.execute("PRAGMA table_info(sessions);").fetchall()
        }
        expected_session_cols = {
            "id",
            "user_id",
            "token_hash",
            "created_at",
            "expires_at",
            "last_seen_at",
            "user_agent_hash",
        }
        assert expected_session_cols.issubset(session_cols.keys())
        assert session_cols["user_id"]["notnull"] == 1
        assert session_cols["token_hash"]["notnull"] == 1

        # Check auth_tokens table
        token_cols = {
            row[1]: {"type": row[2].upper(), "notnull": row[3], "pk": row[5]}
            for row in conn.execute("PRAGMA table_info(auth_tokens);").fetchall()
        }
        expected_token_cols = {
            "id",
            "user_id",
            "purpose",
            "token_hash",
            "expires_at",
            "used_at",
            "created_at",
        }
        assert expected_token_cols.issubset(token_cols.keys())
        assert token_cols["user_id"]["notnull"] == 1
        assert token_cols["purpose"]["notnull"] == 1
        assert token_cols["token_hash"]["notnull"] == 1
    finally:
        conn.close()


def test_users_email_is_unique(tmp_path: Path) -> None:
    """migration test: Verify email column in users has a UNIQUE constraint."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path)

    conn = get_connection(db_path)
    try:
        now = "2026-11-25T12:00:00Z"
        conn.execute(
            """
            INSERT INTO users (
                name, email, password_hash, failed_logins, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            ("User One", "trader@example.com", "argon2id$mockhash", 0, now, now),
        )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO users (
                    name, email, password_hash, failed_logins, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                ("User Two", "trader@example.com", "argon2id$mockhash2", 0, now, now),
            )
    finally:
        conn.close()


def test_user_delete_cascades_to_sessions_and_auth_tokens(tmp_path: Path) -> None:
    """migration test: Verify deleting a user cascades to delete their sessions and auth_tokens."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path)

    conn = get_connection(db_path)
    try:
        now = "2026-11-25T12:00:00Z"
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (
                name, email, password_hash, failed_logins, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            ("Test User", "cascade@example.com", "argon2id$mockhash", 0, now, now),
        )
        user_id = cur.lastrowid
        assert user_id is not None

        # Insert session
        cur.execute(
            """
            INSERT INTO sessions (user_id, token_hash, created_at, expires_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (user_id, "session_token_hash_1", now, now, now),
        )

        # Insert auth token
        cur.execute(
            """
            INSERT INTO auth_tokens (user_id, purpose, token_hash, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (user_id, "verify_email", "auth_token_hash_1", now, now),
        )

        # Delete user
        cur.execute("DELETE FROM users WHERE id = ?;", (user_id,))

        # Verify cascades
        sess_count = cur.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ?;", (user_id,)
        ).fetchone()[0]
        token_count = cur.execute(
            "SELECT COUNT(*) FROM auth_tokens WHERE user_id = ?;", (user_id,)
        ).fetchone()[0]

        assert sess_count == 0, "Deleting user must cascade to delete sessions"
        assert token_count == 0, "Deleting user must cascade to delete auth_tokens"
    finally:
        conn.close()


def test_failed_migration_rolls_back(tmp_path: Path) -> None:
    """migration test: Verify each migration runs in one transaction and a failure rolls back."""
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    conn.close()

    # Create a temporary migrations dir with a valid migration then a broken migration
    test_mig_dir = tmp_path / "migrations"
    test_mig_dir.mkdir()

    (test_mig_dir / "0001_good.sql").write_text(
        "CREATE TABLE test_table (id INTEGER PRIMARY KEY, val TEXT NOT NULL);",
        encoding="utf-8",
    )
    (test_mig_dir / "0002_bad.sql").write_text(
        "CREATE TABLE test_table_2 (id INTEGER PRIMARY KEY); SYNTAX ERROR HERE;",
        encoding="utf-8",
    )

    with pytest.raises(sqlite3.OperationalError):
        run_migrations(db_path, migrations_dir=test_mig_dir)

    conn = get_connection(db_path)
    try:
        # Check that 0001 was applied
        applied = [
            row[0] for row in conn.execute("SELECT version FROM schema_migrations;").fetchall()
        ]
        assert 1 in applied
        assert 2 not in applied

        # And test_table_2 should not exist because 0002 rolled back
        t2_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table_2';"
        ).fetchone()
        assert t2_exists is None, "Failed migration must roll back completely"
    finally:
        conn.close()


def test_migrations_are_idempotent(tmp_path: Path) -> None:
    """migration test: Verify running migrations multiple times succeeds without error."""
    db_path = tmp_path / "test.db"
    applied_first = run_migrations(db_path)
    applied_second = run_migrations(db_path)

    assert applied_first >= 1
    assert applied_second == 0


def test_0002_runs_table_and_columns_exist(tmp_path: Path) -> None:
    """migration test: Verify runs table has columns, types, and index.

    Follows DATABASE.md §1 (AC-7, T-6).
    """
    db_path = tmp_path / "test.db"
    run_migrations(db_path)

    conn = get_connection(db_path)
    try:
        run_cols = {
            row[1]: {"type": row[2].upper(), "notnull": row[3], "pk": row[5]}
            for row in conn.execute("PRAGMA table_info(runs);").fetchall()
        }
        expected_run_cols = {
            "id",
            "user_id",
            "name",
            "seed",
            "config_json",
            "fingerprint",
            "provenance",
            "result_json",
            "schema_version",
            "created_at",
        }
        assert expected_run_cols.issubset(run_cols.keys())
        assert run_cols["id"]["pk"] == 1
        assert run_cols["id"]["type"] == "TEXT"
        assert run_cols["user_id"]["notnull"] == 1
        assert run_cols["name"]["notnull"] == 1
        assert run_cols["seed"]["notnull"] == 1
        assert run_cols["config_json"]["notnull"] == 1
        assert run_cols["fingerprint"]["notnull"] == 1
        assert run_cols["provenance"]["notnull"] == 1
        assert run_cols["result_json"]["notnull"] == 1
        assert run_cols["schema_version"]["notnull"] == 1
        assert run_cols["created_at"]["notnull"] == 1

        # Check index
        indices = conn.execute("PRAGMA index_list(runs);").fetchall()
        idx_names = [idx[1] for idx in indices]
        assert "idx_runs_user_created" in idx_names
    finally:
        conn.close()


def test_0002_runs_cascade_on_user_delete(tmp_path: Path) -> None:
    """migration test: Verify deleting a user cascades to delete their runs (AC-6, AC-7, T-6)."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path)

    conn = get_connection(db_path)
    try:
        now = "2026-11-25T12:00:00Z"
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (
                name, email, password_hash, failed_logins, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            ("Runner User", "runner@example.com", "argon2id$mockhash", 0, now, now),
        )
        user_id = cur.lastrowid
        assert user_id is not None

        cur.execute(
            """
            INSERT INTO runs (
                id, user_id, name, seed, config_json, fingerprint,
                provenance, result_json, schema_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "run-uuid-1",
                user_id,
                "Test Run",
                42,
                "{}",
                "a1b2c3d4e5f6",
                "SYNTHETIC",
                "{}",
                1,
                now,
            ),
        )

        # Confirm run exists
        assert (
            cur.execute("SELECT COUNT(*) FROM runs WHERE user_id = ?;", (user_id,)).fetchone()[0]
            == 1
        )

        # Delete user
        cur.execute("DELETE FROM users WHERE id = ?;", (user_id,))

        # Verify run was cascade deleted
        assert (
            cur.execute("SELECT COUNT(*) FROM runs WHERE user_id = ?;", (user_id,)).fetchone()[0]
            == 0
        )
    finally:
        conn.close()
