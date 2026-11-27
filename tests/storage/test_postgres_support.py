"""Offline tests for PostgreSQL DATABASE_URL config and SQL translation."""

from pathlib import Path
from typing import Any

import pytest

from opentrade.config import ValidationError, load_settings
from opentrade.storage.db import transaction
from opentrade.storage.migrate import DEFAULT_MIGRATIONS_DIR, split_sql_statements
from opentrade.storage.postgres_compat import (
    PostgresConnectionWrapper,
    is_postgres_url,
    translate_sql_to_postgres,
)


class _FakePgCursor:
    def __init__(self, log: list[tuple[str, Any]]) -> None:
        self._log = log
        self._rows: list[tuple[Any, ...]] = []

    def execute(self, sql: str, params: Any = None) -> None:
        self._log.append((sql, params))
        if "RETURNING id" in sql:
            self._rows = [(42,)]
        else:
            self._rows = []

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Any]:
        return list(self._rows)

    def close(self) -> None:
        pass


class _FakePgConn:
    def __init__(self) -> None:
        self.log: list[tuple[str, Any]] = []

    def cursor(self) -> _FakePgCursor:
        return _FakePgCursor(self.log)

    def commit(self) -> None:
        self.log.append(("COMMIT", None))

    def rollback(self) -> None:
        self.log.append(("ROLLBACK", None))

    def close(self) -> None:
        pass


def test_database_url_config_parsing_and_ssl_in_production() -> None:
    """DATABASE_URL parses postgresql/postgres URIs, enforces SSL in prod, and redacts repr."""
    s_dev = load_settings(
        overrides={
            "OPENTRADE_ENV": "local",
            "OPENTRADE_SECRET_KEY": "a" * 32,
            "OPENTRADE_BASE_URL": "http://localhost:8501",
            "DATABASE_URL": "postgresql://user:secretpass@localhost:5432/opentrade",
        }
    )
    assert s_dev.database_url == "postgresql://user:secretpass@localhost:5432/opentrade"
    assert "secretpass" not in repr(s_dev)
    assert "[REDACTED]" in repr(s_dev)

    s_prod = load_settings(
        overrides={
            "OPENTRADE_ENV": "production",
            "OPENTRADE_SECRET_KEY": "a" * 32,
            "OPENTRADE_BASE_URL": "https://opentrade.example.com",
            "SMTP_HOST": "smtp.example.com",
            "SMTP_USER": "mailer",
            "SMTP_PASSWORD": "pw",
            "SMTP_FROM": "noreply@example.com",
            "DATABASE_URL": "postgres://user:secretpass@db.example.com:5432/opentrade",
        }
    )
    assert s_prod.database_url is not None
    assert s_prod.database_url.endswith("?sslmode=require")

    with pytest.raises(ValidationError, match="DATABASE_URL"):
        load_settings(
            overrides={
                "OPENTRADE_ENV": "local",
                "OPENTRADE_SECRET_KEY": "a" * 32,
                "OPENTRADE_BASE_URL": "http://localhost:8501",
                "DATABASE_URL": "mysql://user:pw@localhost/db",
            }
        )


def test_postgres_sql_and_migration_translation() -> None:
    """All 0001-0005 migrations and repository SQL translate cleanly to PostgreSQL."""
    assert is_postgres_url("postgresql://u:p@h:5432/d") is True
    assert is_postgres_url("postgres://u:p@h:5432/d") is True
    assert is_postgres_url("./data/opentrade.db") is False

    # Placeholders outside quotes only
    q = translate_sql_to_postgres("SELECT * FROM users WHERE email = ? AND name = 'why?';")
    assert q == "SELECT * FROM users WHERE email = %s AND name = 'why?';"

    # INSERT OR IGNORE -> ON CONFLICT DO NOTHING
    ins = translate_sql_to_postgres(
        "INSERT OR IGNORE INTO watchlist_items (user_id, symbol, added_at) VALUES (?, ?, ?);"
    )
    assert "INSERT OR IGNORE" not in ins
    assert "ON CONFLICT DO NOTHING;" in ins
    assert ins.count("%s") == 3

    # Verify all numbered migrations translate without AUTOINCREMENT remaining
    for mig in sorted(Path(DEFAULT_MIGRATIONS_DIR).glob("*.sql")):
        for stmt in split_sql_statements(mig.read_text(encoding="utf-8")):
            pg_stmt = translate_sql_to_postgres(stmt)
            assert "AUTOINCREMENT" not in pg_stmt.upper()


def test_postgres_wrapper_returning_id_and_transaction() -> None:
    """PostgresConnectionWrapper populates lastrowid via RETURNING id and uses BEGIN/COMMIT."""
    raw = _FakePgConn()
    conn = PostgresConnectionWrapper(raw)
    with transaction(conn) as cur:
        cur.execute(
            "INSERT INTO users (name, email) VALUES (?, ?);",
            ("Alice", "alice@example.com"),
        )
        assert cur.lastrowid == 42

    executed_sql = [entry[0] for entry in raw.log]
    assert executed_sql[0] == "BEGIN;"
    assert "RETURNING id;" in executed_sql[1]
    assert executed_sql[-1] == "COMMIT;"
