"""
StockSense AI - Conversational Session Store

Maintains short-lived in-memory conversational context per session_id.
Enables multi-turn corrections ("Illa, 5 illa 3 packet"), follow-up confirmations,
and context-aware clarification without executing stale or cancelled actions.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

SESSION_TIMEOUT_MINUTES = 15


class SessionStore:
    """In-memory thread-safe session store with auto-expiry."""

    _sessions: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def _cleanup_expired(cls):
        now = datetime.now(timezone.utc)
        expired_keys = [
            sid for sid, data in cls._sessions.items()
            if (now - data.get("updated_at", now)) > timedelta(minutes=SESSION_TIMEOUT_MINUTES)
        ]
        for sid in expired_keys:
            cls._sessions.pop(sid, None)

    @classmethod
    def get_session(cls, session_id: Optional[str]) -> Dict[str, Any]:
        if not session_id:
            return {"history": [], "pending_proposal": None}
        cls._cleanup_expired()
        if session_id not in cls._sessions:
            cls._sessions[session_id] = {
                "history": [],
                "pending_proposal": None,
                "updated_at": datetime.now(timezone.utc),
            }
        cls._sessions[session_id]["updated_at"] = datetime.now(timezone.utc)
        return cls._sessions[session_id]

    @classmethod
    def append_turn(cls, session_id: Optional[str], role: str, text: str):
        if not session_id or not text:
            return
        session = cls.get_session(session_id)
        history = session.setdefault("history", [])
        history.append({"role": role, "content": text})
        # Keep last 8 turns
        if len(history) > 8:
            session["history"] = history[-8:]
        session["updated_at"] = datetime.now(timezone.utc)

    @classmethod
    def get_context_history(cls, session_id: Optional[str]) -> List[Dict[str, str]]:
        if not session_id:
            return []
        session = cls.get_session(session_id)
        return session.get("history", [])

    @classmethod
    def set_pending_proposal(cls, session_id: Optional[str], proposal: Dict[str, Any]):
        if not session_id:
            return
        session = cls.get_session(session_id)
        session["pending_proposal"] = proposal
        session["updated_at"] = datetime.now(timezone.utc)

    @classmethod
    def get_pending_proposal(cls, session_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not session_id:
            return None
        session = cls.get_session(session_id)
        return session.get("pending_proposal")

    @classmethod
    def update_pending_proposal(cls, session_id: Optional[str], updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not session_id:
            return None
        session = cls.get_session(session_id)
        current = session.get("pending_proposal")
        if not current:
            return None
        current.update(updates)
        session["pending_proposal"] = current
        session["updated_at"] = datetime.now(timezone.utc)
        return current

    @classmethod
    def clear_pending_proposal(cls, session_id: Optional[str]):
        if not session_id:
            return
        session = cls.get_session(session_id)
        session["pending_proposal"] = None
        session["updated_at"] = datetime.now(timezone.utc)

    @classmethod
    def clear_session(cls, session_id: Optional[str]):
        if not session_id:
            return
        cls._sessions.pop(session_id, None)
