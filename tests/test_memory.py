from pathlib import Path

from app.domain.enums import IssueType
from app.domain.models import ConversationState
from app.memory.sqlite_store import SQLiteConversationStore


def test_sqlite_store_round_trip(tmp_path: Path) -> None:
    store = SQLiteConversationStore(tmp_path / "state.sqlite3")
    state = ConversationState(
        conversation_id="abc",
        active_driver_id="D-LON-001",
        last_issue_type=IssueType.AIRPORT_SHORT_FARE,
        messages=[{"role": "user", "content": "hello"}],
    )
    store.save(state)
    loaded = store.load("abc")
    assert loaded == state


def test_sqlite_store_returns_none_for_unknown(tmp_path: Path) -> None:
    store = SQLiteConversationStore(tmp_path / "state.sqlite3")
    assert store.load("missing") is None


def test_sqlite_store_upserts(tmp_path: Path) -> None:
    store = SQLiteConversationStore(tmp_path / "state.sqlite3")
    store.save(ConversationState(conversation_id="abc"))
    store.save(ConversationState(conversation_id="abc", active_driver_id="D-LON-003"))
    assert store.load("abc").active_driver_id == "D-LON-003"
