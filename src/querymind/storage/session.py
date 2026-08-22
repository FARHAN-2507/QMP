"""Session store — file-based persistent storage for conversation history.

Stores sessions as JSON files in a hidden directory.
Auto-cleans old sessions based on TTL.
"""

from __future__ import annotations

import json
import logging
import secrets
import string
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def generate_session_id(length: int = 8) -> str:
    """Generate a random session ID."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class SessionStore:
    """File-based session storage with auto-cleanup."""

    def __init__(self, data_dir: Path | str) -> None:
        self._base_dir = Path(data_dir).expanduser()
        self._history_dir = self._base_dir / ".history"
        self._history_dir.mkdir(parents=True, exist_ok=True)
        self._current_file = self._history_dir / ".current_session"

    def save(
        self,
        session_id: str,
        messages: list[dict[str, str]],
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Save a session to disk."""
        now = datetime.now(UTC)
        session_file = self._history_dir / f"{session_id}.json"

        # Load existing to preserve created_at
        existing = self.load(session_id)
        created_at = existing.get("created_at", now.isoformat()) if existing else now.isoformat()

        data = {
            "session_id": session_id,
            "created_at": created_at,
            "updated_at": now.isoformat(),
            "messages": messages,
            "metadata": {
                "total_messages": len(messages),
                **(metadata or {}),
            },
        }

        session_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        logger.debug("Saved session %s (%d messages)", session_id, len(messages))
        return session_file

    def load(self, session_id: str) -> dict[str, Any] | None:
        """Load a session from disk."""
        session_file = self._history_dir / f"{session_id}.json"
        if not session_file.exists():
            return None

        try:
            return json.loads(session_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load session %s: %s", session_id, e)
            return None

    def list_sessions(self, ttl_days: int = 30) -> list[dict[str, Any]]:
        """List all sessions, sorted by most recent first.

        Only returns sessions newer than ttl_days.
        """
        cutoff = datetime.now(UTC) - timedelta(days=ttl_days)
        sessions: list[dict[str, Any]] = []

        for f in self._history_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                updated_at = datetime.fromisoformat(data.get("updated_at", ""))
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=UTC)
                if updated_at >= cutoff:
                    sessions.append({
                        "session_id": data.get("session_id"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "total_messages": data.get("metadata", {}).get("total_messages", 0),
                    })
            except (json.JSONDecodeError, OSError, ValueError):
                continue

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return sessions

    def delete(self, session_id: str) -> bool:
        """Delete a session file."""
        session_file = self._history_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            logger.debug("Deleted session %s", session_id)
            return True
        return False

    def get_current_session_id(self) -> str | None:
        """Get the current session ID."""
        if not self._current_file.exists():
            return None
        try:
            return self._current_file.read_text().strip()
        except OSError:
            return None

    def set_current_session_id(self, session_id: str) -> None:
        """Set the current session ID."""
        self._current_file.write_text(session_id)

    def create_new_session(self) -> str:
        """Create a new session and set it as current."""
        session_id = generate_session_id()
        self.set_current_session_id(session_id)
        return session_id

    def cleanup_old_sessions(self, ttl_days: int = 30) -> int:
        """Delete sessions older than ttl_days. Returns count deleted."""
        cutoff = datetime.now(UTC) - timedelta(days=ttl_days)
        deleted = 0

        for f in self._history_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                updated_at = datetime.fromisoformat(data.get("updated_at", ""))
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=UTC)
                if updated_at < cutoff:
                    f.unlink()
                    deleted += 1
                    logger.debug("Cleaned up old session: %s", f.stem)
            except (json.JSONDecodeError, OSError, ValueError):
                continue

        if deleted > 0:
            logger.info("Cleaned up %d old sessions", deleted)
        return deleted

    def session_exists(self, session_id: str) -> bool:
        """Check if a session file exists."""
        return (self._history_dir / f"{session_id}.json").exists()
