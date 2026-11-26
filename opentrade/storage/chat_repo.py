"""Repository for chat_messages and pending_actions using parameterized SQL (T22.1-T22.3)."""

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatMessageRow:
    """Database row for chat_messages."""

    id: int
    user_id: int
    role: str
    content: str
    created_at: str
    deleted_at: str | None


@dataclass(frozen=True)
class PendingActionRow:
    """Database row for pending_actions."""

    id: str
    user_id: int
    action: str
    payload_json: str
    status: str
    expires_at: str
    created_at: str


class ChatRepository:
    """SQLite repository for user-scoped chat messages and pending actions."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add_message(self, user_id: int, role: str, content: str, created_at: str) -> int:
        """Insert a chat message and return its row ID."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO chat_messages (user_id, role, content, created_at, deleted_at)
                VALUES (?, ?, ?, ?, NULL);
                """,
                (user_id, role, content, created_at),
            )
            return int(cursor.lastrowid or 0)
        finally:
            cursor.close()

    def list_active_messages(self, user_id: int) -> list[ChatMessageRow]:
        """Return non-deleted chat messages for user_id in chronological order."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, user_id, role, content, created_at, deleted_at
                FROM chat_messages
                WHERE user_id = ? AND deleted_at IS NULL
                ORDER BY id ASC;
                """,
                (user_id,),
            )
            return [
                ChatMessageRow(
                    id=r[0],
                    user_id=r[1],
                    role=r[2],
                    content=r[3],
                    created_at=r[4],
                    deleted_at=r[5],
                )
                for r in cursor.fetchall()
            ]
        finally:
            cursor.close()

    def count_user_turns_since(self, user_id: int, since_iso: str) -> int:
        """Count user messages sent since since_iso (including soft-deleted turns for quota)."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM chat_messages
                WHERE user_id = ? AND role = 'user' AND created_at >= ?;
                """,
                (user_id, since_iso),
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        finally:
            cursor.close()

    def soft_delete_messages(self, user_id: int, deleted_at: str) -> int:
        """Soft-delete all active messages for user_id."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE chat_messages
                SET deleted_at = ?
                WHERE user_id = ? AND deleted_at IS NULL;
                """,
                (deleted_at, user_id),
            )
            return cursor.rowcount
        finally:
            cursor.close()

    def create_pending_action(
        self,
        action_id: str,
        user_id: int,
        action: str,
        payload_json: str,
        expires_at: str,
        created_at: str,
    ) -> PendingActionRow:
        """Insert a PENDING action row."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO pending_actions (
                    id, user_id, action, payload_json, status, expires_at, created_at
                ) VALUES (?, ?, ?, ?, 'PENDING', ?, ?);
                """,
                (action_id, user_id, action, payload_json, expires_at, created_at),
            )
            return PendingActionRow(
                id=action_id,
                user_id=user_id,
                action=action,
                payload_json=payload_json,
                status="PENDING",
                expires_at=expires_at,
                created_at=created_at,
            )
        finally:
            cursor.close()

    def get_pending_action(self, action_id: str, user_id: int) -> PendingActionRow | None:
        """Fetch a pending action strictly scoped to user_id."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, user_id, action, payload_json, status, expires_at, created_at
                FROM pending_actions
                WHERE id = ? AND user_id = ?;
                """,
                (action_id, user_id),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return PendingActionRow(
                id=r[0],
                user_id=r[1],
                action=r[2],
                payload_json=r[3],
                status=r[4],
                expires_at=r[5],
                created_at=r[6],
            )
        finally:
            cursor.close()

    def update_action_status(self, action_id: str, user_id: int, status: str) -> int:
        """Update pending action status strictly scoped to user_id."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE pending_actions SET status = ? WHERE id = ? AND user_id = ?;",
                (status, action_id, user_id),
            )
            return cursor.rowcount
        finally:
            cursor.close()
