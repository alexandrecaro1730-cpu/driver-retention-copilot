"""SQLite conversation state store.

Business intent: multi-turn managers can ask follow-ups without repeating the driver ID, while the
system persists only the minimum context needed for operational continuity.

Technical intent: SQLite gives a dependency-free durable checkpoint for the take-home. Production
can replace it with Postgres/Redis behind the same ``load``/``save`` interface.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.domain.models import ConversationState


class SQLiteConversationStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._initialise()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path, timeout=5)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=5000")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialise(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def load(self, conversation_id: str) -> ConversationState | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT state_json FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        if row is None:
            return None
        return ConversationState.model_validate(json.loads(row[0]))

    def save(self, state: ConversationState) -> None:
        serialised = state.model_dump_json(exclude_computed_fields=True)
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO conversations (conversation_id, state_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (state.conversation_id, serialised),
            )
