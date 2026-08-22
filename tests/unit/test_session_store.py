"""Tests for file-based session storage."""

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from querymind.storage.session import SessionStore, generate_session_id


def test_generate_session_id() -> None:
    id1 = generate_session_id()
    id2 = generate_session_id()
    assert len(id1) == 8
    assert id1 != id2
    assert id1.isalnum()


def test_session_store_creates_directory() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        SessionStore(tmpdir)
        assert (Path(tmpdir) / ".history").exists()


def test_session_store_save_and_load() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(tmpdir)
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        store.save("test123", messages, {"tool_calls": 2})

        data = store.load("test123")
        assert data is not None
        assert data["session_id"] == "test123"
        assert len(data["messages"]) == 2
        assert data["messages"][0]["content"] == "Hello"


def test_session_store_load_nonexistent() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(tmpdir)
        assert store.load("nonexistent") is None


def test_session_store_list_sessions() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(tmpdir)
        store.save("s1", [{"role": "user", "content": "test1"}])
        store.save("s2", [{"role": "user", "content": "test2"}])

        sessions = store.list_sessions()
        assert len(sessions) == 2
        session_ids = {s["session_id"] for s in sessions}
        assert "s1" in session_ids
        assert "s2" in session_ids


def test_session_store_delete() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(tmpdir)
        store.save("del1", [{"role": "user", "content": "test"}])
        assert store.session_exists("del1")

        result = store.delete("del1")
        assert result is True
        assert not store.session_exists("del1")


def test_session_store_delete_nonexistent() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(tmpdir)
        result = store.delete("nonexistent")
        assert result is False


def test_session_store_current_session() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(tmpdir)
        assert store.get_current_session_id() is None

        store.set_current_session_id("abc123")
        assert store.get_current_session_id() == "abc123"


def test_session_store_create_new_session() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(tmpdir)
        session_id = store.create_new_session()
        assert len(session_id) == 8
        assert store.get_current_session_id() == session_id


def test_session_store_cleanup_old_sessions() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(tmpdir)

        # Create old session (60 days ago)
        old_data = {
            "session_id": "old",
            "created_at": (datetime.now(UTC) - timedelta(days=60)).isoformat(),
            "updated_at": (datetime.now(UTC) - timedelta(days=60)).isoformat(),
            "messages": [],
        }
        (Path(tmpdir) / ".history" / "old.json").write_text(json.dumps(old_data))

        # Create recent session
        store.save("new", [{"role": "user", "content": "test"}])

        deleted = store.cleanup_old_sessions(ttl_days=30)
        assert deleted == 1
        assert not store.session_exists("old")
        assert store.session_exists("new")


def test_session_store_preserves_created_at() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(tmpdir)
        store.save("pres1", [{"role": "user", "content": "first"}])
        created = store.load("pres1")["created_at"]

        # Update the session
        store.save("pres1", [{"role": "user", "content": "updated"}])
        updated = store.load("pres1")["created_at"]

        # created_at should be preserved
        assert created == updated


def test_session_exists() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SessionStore(tmpdir)
        assert not store.session_exists("test")
        store.save("test", [])
        assert store.session_exists("test")
