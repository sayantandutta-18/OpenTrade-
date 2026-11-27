"""Database repositories using strictly parameterized SQL per docs/DATABASE.md."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class UserRow:
    """Immutable representation of a row in the users table."""

    id: int
    name: str
    email: str
    password_hash: str
    email_verified_at: str | None
    failed_logins: int
    locked_until: str | None
    created_at: str
    updated_at: str
    terms_accepted_at: str | None = None


class UserRepository:
    """Repository handling all SQL queries for the users table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(
        self,
        name: str,
        email: str,
        password_hash: str,
        created_at: str,
        updated_at: str,
        terms_accepted_at: str | None = None,
    ) -> UserRow:
        """Insert a new user row using parameterized SQL.

        Args:
            name: User full name.
            email: Lowercase email address.
            password_hash: Salted Argon2id password hash.
            created_at: ISO 8601 UTC creation timestamp.
            updated_at: ISO 8601 UTC update timestamp.
            terms_accepted_at: Optional ISO 8601 UTC Terms & Conditions acceptance timestamp.

        Returns:
            UserRow: Newly inserted user record.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO users (
                    name, email, password_hash, email_verified_at,
                    failed_logins, locked_until, created_at, updated_at, terms_accepted_at
                ) VALUES (?, ?, ?, NULL, 0, NULL, ?, ?, ?);
                """,
                (name, email, password_hash, created_at, updated_at, terms_accepted_at),
            )
            user_id = cursor.lastrowid
            if user_id is None:
                raise RuntimeError("Failed to retrieve lastrowid after user insert")
            return UserRow(
                id=user_id,
                name=name,
                email=email,
                password_hash=password_hash,
                email_verified_at=None,
                failed_logins=0,
                locked_until=None,
                created_at=created_at,
                updated_at=updated_at,
                terms_accepted_at=terms_accepted_at,
            )
        finally:
            cursor.close()

    def get_by_id(self, user_id: int) -> UserRow | None:
        """Fetch a user row by primary key id using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, name, email, password_hash, email_verified_at,
                       failed_logins, locked_until, created_at, updated_at, terms_accepted_at
                FROM users WHERE id = ?;
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return UserRow(
                id=row[0],
                name=row[1],
                email=row[2],
                password_hash=row[3],
                email_verified_at=row[4],
                failed_logins=row[5],
                locked_until=row[6],
                created_at=row[7],
                updated_at=row[8],
                terms_accepted_at=row[9],
            )
        finally:
            cursor.close()

    def get_by_email(self, email: str) -> UserRow | None:
        """Fetch a user row by lowercase email using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, name, email, password_hash, email_verified_at,
                       failed_logins, locked_until, created_at, updated_at, terms_accepted_at
                FROM users WHERE email = ?;
                """,
                (email.strip().lower(),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return UserRow(
                id=row[0],
                name=row[1],
                email=row[2],
                password_hash=row[3],
                email_verified_at=row[4],
                failed_logins=row[5],
                locked_until=row[6],
                created_at=row[7],
                updated_at=row[8],
                terms_accepted_at=row[9],
            )
        finally:
            cursor.close()

    def update_email_verified_at(self, user_id: int, verified_at: str) -> None:
        """Update email_verified_at timestamp for a given user using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE users
                SET email_verified_at = ?, updated_at = ?
                WHERE id = ?;
                """,
                (verified_at, verified_at, user_id),
            )
        finally:
            cursor.close()

    def record_failed_login(
        self,
        user_id: int,
        failed_logins: int,
        locked_until: str | None,
        updated_at: str,
    ) -> None:
        """Record a failed login attempt and optional lockout using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE users
                SET failed_logins = ?, locked_until = ?, updated_at = ?
                WHERE id = ?;
                """,
                (failed_logins, locked_until, updated_at, user_id),
            )
        finally:
            cursor.close()

    def reset_failed_logins(self, user_id: int, updated_at: str) -> None:
        """Reset failed logins counter and clear lockout timestamp using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE users
                SET failed_logins = 0, locked_until = NULL, updated_at = ?
                WHERE id = ?;
                """,
                (updated_at, user_id),
            )
        finally:
            cursor.close()

    def update_password_hash(self, user_id: int, password_hash: str, updated_at: str) -> None:
        """Update password_hash, reset failed_logins, and clear lockout using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE users
                SET password_hash = ?, failed_logins = 0, locked_until = NULL, updated_at = ?
                WHERE id = ?;
                """,
                (password_hash, updated_at, user_id),
            )
        finally:
            cursor.close()

    def update_profile(
        self,
        user_id: int,
        name: str,
        email: str,
        email_verified_at: str | None,
        updated_at: str,
    ) -> None:
        """Update user profile (name, email, email_verified_at) using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE users
                SET name = ?, email = ?, email_verified_at = ?, updated_at = ?
                WHERE id = ?;
                """,
                (name, email.strip().lower(), email_verified_at, updated_at, user_id),
            )
        finally:
            cursor.close()

    def count(self) -> int:
        """Count total rows in the users table."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users;")
            result = cursor.fetchone()
            return int(result[0]) if result else 0
        finally:
            cursor.close()

    def delete(self, user_id: int) -> int:
        """Delete a user row by primary key id using parameterized SQL.

        Triggers SQLite ON DELETE CASCADE across child tables (sessions, auth_tokens, etc.).
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM users WHERE id = ?;", (user_id,))
            return cursor.rowcount
        finally:
            cursor.close()


@dataclass(frozen=True)
class AuthTokenRow:
    """Immutable representation of a row in the auth_tokens table."""

    id: int
    user_id: int
    purpose: str
    token_hash: str
    expires_at: str
    used_at: str | None
    created_at: str


class TokenRepository:
    """Repository handling all SQL queries for the auth_tokens table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(
        self,
        user_id: int,
        purpose: str,
        token_hash: str,
        expires_at: str,
        created_at: str,
    ) -> AuthTokenRow:
        """Insert a new auth token row using parameterized SQL.

        Args:
            user_id: Foreign key to users.id.
            purpose: Token purpose (e.g. 'verify_email', 'reset_password').
            token_hash: SHA-256 hex digest of the raw token.
            expires_at: ISO 8601 UTC expiration timestamp.
            created_at: ISO 8601 UTC creation timestamp.

        Returns:
            AuthTokenRow: Newly created token row.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO auth_tokens (
                    user_id, purpose, token_hash, expires_at, used_at, created_at
                ) VALUES (?, ?, ?, ?, NULL, ?);
                """,
                (user_id, purpose, token_hash, expires_at, created_at),
            )
            token_id = cursor.lastrowid
            if token_id is None:
                raise RuntimeError("Failed to retrieve lastrowid after token insert")
            return AuthTokenRow(
                id=token_id,
                user_id=user_id,
                purpose=purpose,
                token_hash=token_hash,
                expires_at=expires_at,
                used_at=None,
                created_at=created_at,
            )
        finally:
            cursor.close()

    def get_by_hash(self, token_hash: str) -> AuthTokenRow | None:
        """Fetch an auth token row by token_hash using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, user_id, purpose, token_hash, expires_at, used_at, created_at
                FROM auth_tokens WHERE token_hash = ?;
                """,
                (token_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return AuthTokenRow(
                id=row[0],
                user_id=row[1],
                purpose=row[2],
                token_hash=row[3],
                expires_at=row[4],
                used_at=row[5],
                created_at=row[6],
            )
        finally:
            cursor.close()

    def mark_used(self, token_id: int, used_at: str) -> None:
        """Mark an auth token as used using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE auth_tokens SET used_at = ? WHERE id = ?;",
                (used_at, token_id),
            )
        finally:
            cursor.close()

    def invalidate_unused_verification_tokens(self, user_id: int, invalid_at: str) -> None:
        """Invalidate earlier unused verification tokens for a user by expiring them."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE auth_tokens
                SET expires_at = ?
                WHERE user_id = ?
                  AND purpose IN ('verify_email', 'resend_verify_email')
                  AND used_at IS NULL;
                """,
                (invalid_at, user_id),
            )
        finally:
            cursor.close()

    def invalidate_unused_tokens(self, user_id: int, purpose: str, invalid_at: str) -> None:
        """Invalidate earlier unused tokens for a user and purpose by expiring them."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE auth_tokens
                SET expires_at = ?
                WHERE user_id = ? AND purpose = ? AND used_at IS NULL;
                """,
                (invalid_at, user_id, purpose),
            )
        finally:
            cursor.close()

    def count_recent_tokens(self, user_id: int, purpose: str, since_iso: str) -> int:
        """Count tokens issued for a user and purpose since a given timestamp."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT COUNT(*) FROM auth_tokens
                WHERE user_id = ? AND purpose = ? AND created_at >= ?;
                """,
                (user_id, purpose, since_iso),
            )
            result = cursor.fetchone()
            return int(result[0]) if result else 0
        finally:
            cursor.close()


@dataclass(frozen=True)
class SessionRow:
    """Immutable representation of a row in the sessions table."""

    id: int
    user_id: int
    token_hash: str
    created_at: str
    expires_at: str
    last_seen_at: str
    user_agent_hash: str | None


class SessionRepository:
    """Repository handling all SQL queries for the sessions table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(
        self,
        user_id: int,
        token_hash: str,
        expires_at: str,
        created_at: str,
        last_seen_at: str,
        user_agent_hash: str | None = None,
    ) -> SessionRow:
        """Insert a new session row using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO sessions (
                    user_id, token_hash, created_at, expires_at, last_seen_at, user_agent_hash
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (user_id, token_hash, created_at, expires_at, last_seen_at, user_agent_hash),
            )
            session_id = cursor.lastrowid
            if session_id is None:
                raise RuntimeError("Failed to retrieve lastrowid after session insert")
            return SessionRow(
                id=session_id,
                user_id=user_id,
                token_hash=token_hash,
                created_at=created_at,
                expires_at=expires_at,
                last_seen_at=last_seen_at,
                user_agent_hash=user_agent_hash,
            )
        finally:
            cursor.close()

    def get_by_hash(self, token_hash: str) -> SessionRow | None:
        """Fetch a session by token_hash using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, user_id, token_hash, created_at, expires_at,
                       last_seen_at, user_agent_hash
                FROM sessions WHERE token_hash = ?;
                """,
                (token_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return SessionRow(
                id=row[0],
                user_id=row[1],
                token_hash=row[2],
                created_at=row[3],
                expires_at=row[4],
                last_seen_at=row[5],
                user_agent_hash=row[6],
            )
        finally:
            cursor.close()

    def touch(self, session_id: int, last_seen_at: str, expires_at: str) -> None:
        """Update last_seen_at and expires_at using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE sessions
                SET last_seen_at = ?, expires_at = ?
                WHERE id = ?;
                """,
                (last_seen_at, expires_at, session_id),
            )
        finally:
            cursor.close()

    def delete_by_id(self, session_id: int) -> None:
        """Delete a session by primary key id using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM sessions WHERE id = ?;", (session_id,))
        finally:
            cursor.close()

    def delete_by_hash(self, token_hash: str) -> None:
        """Delete a session by token_hash using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM sessions WHERE token_hash = ?;", (token_hash,))
        finally:
            cursor.close()

    def delete_all_for_user(self, user_id: int) -> int:
        """Delete all sessions for a user using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM sessions WHERE user_id = ?;", (user_id,))
            return cursor.rowcount
        finally:
            cursor.close()

    def delete_other_sessions(self, user_id: int, current_token_hash: str) -> int:
        """Delete all sessions for a user except current_token_hash using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                DELETE FROM sessions
                WHERE user_id = ? AND token_hash != ?;
                """,
                (user_id, current_token_hash),
            )
            return cursor.rowcount
        finally:
            cursor.close()

    def count_for_user(self, user_id: int) -> int:
        """Count active sessions for a user using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ?;", (user_id,))
            result = cursor.fetchone()
            return int(result[0]) if result else 0
        finally:
            cursor.close()


@dataclass(frozen=True)
class RunRow:
    """Immutable representation of a row in the runs table per docs/DATABASE.md."""

    id: str
    user_id: int
    name: str
    seed: int
    config_json: str
    fingerprint: str
    provenance: str
    result_json: str
    schema_version: int
    created_at: str


class RunRepository:
    """Repository handling all SQL queries for the runs table per docs/DATABASE.md."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(
        self,
        id: str,
        user_id: int,
        name: str,
        seed: int,
        config_json: str,
        fingerprint: str,
        provenance: str,
        result_json: str,
        schema_version: int,
        created_at: str,
    ) -> RunRow:
        """Insert a new run row using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO runs (
                    id, user_id, name, seed, config_json, fingerprint,
                    provenance, result_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    id,
                    user_id,
                    name,
                    seed,
                    config_json,
                    fingerprint,
                    provenance,
                    result_json,
                    schema_version,
                    created_at,
                ),
            )
            return RunRow(
                id=id,
                user_id=user_id,
                name=name,
                seed=seed,
                config_json=config_json,
                fingerprint=fingerprint,
                provenance=provenance,
                result_json=result_json,
                schema_version=schema_version,
                created_at=created_at,
            )
        finally:
            cursor.close()

    def get_by_id_and_user_id(self, run_id: str, user_id: int) -> RunRow | None:
        """Fetch a run row by run_id and user_id using parameterized SQL.

        SECURITY.md T-6: Every query filters by user_id to enforce cross-user access isolation.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, user_id, name, seed, config_json, fingerprint,
                       provenance, result_json, schema_version, created_at
                FROM runs
                WHERE id = ? AND user_id = ?;
                """,
                (run_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return RunRow(
                id=row[0],
                user_id=row[1],
                name=row[2],
                seed=row[3],
                config_json=row[4],
                fingerprint=row[5],
                provenance=row[6],
                result_json=row[7],
                schema_version=row[8],
                created_at=row[9],
            )
        finally:
            cursor.close()

    def delete_by_id_and_user_id(self, run_id: str, user_id: int) -> int:
        """Delete a run by run_id and user_id using parameterized SQL.

        Returns:
            int: Number of deleted rows (1 if deleted, 0 if not found or belongs to another user).
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM runs WHERE id = ? AND user_id = ?;",
                (run_id, user_id),
            )
            return cursor.rowcount
        finally:
            cursor.close()

    def list_by_user_id(
        self,
        user_id: int,
        limit: int = 50,
        cursor_created_at: str | None = None,
    ) -> list[RunRow]:
        """Fetch recent runs for a user using parameterized SQL."""
        cursor = self.conn.cursor()
        try:
            if cursor_created_at:
                cursor.execute(
                    """
                    SELECT id, user_id, name, seed, config_json, fingerprint,
                           provenance, result_json, schema_version, created_at
                    FROM runs
                    WHERE user_id = ? AND created_at < ?
                    ORDER BY created_at DESC
                    LIMIT ?;
                    """,
                    (user_id, cursor_created_at, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, user_id, name, seed, config_json, fingerprint,
                           provenance, result_json, schema_version, created_at
                    FROM runs
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?;
                    """,
                    (user_id, limit),
                )
            rows = cursor.fetchall()
            return [
                RunRow(
                    id=r[0],
                    user_id=r[1],
                    name=r[2],
                    seed=r[3],
                    config_json=r[4],
                    fingerprint=r[5],
                    provenance=r[6],
                    result_json=r[7],
                    schema_version=r[8],
                    created_at=r[9],
                )
                for r in rows
            ]
        finally:
            cursor.close()
