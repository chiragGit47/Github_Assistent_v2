from datetime import datetime, timedelta, timezone
from typing import Optional

from app.schemas.session import SessionState


SESSION_LIFETIME = timedelta(hours=2)


class SessionManager:
    def __init__(self):
        self.sessions: dict[str, SessionState] = {}

    def create(self, session: SessionState) -> None:
        self.cleanup_expired()
        self.sessions[session.session_id] = session

    def get(self, session_id: str) -> Optional[SessionState]:
        self.cleanup_expired()

        session = self.sessions.get(session_id)

        if session is None:
            return None

        session.last_activity = datetime.now(timezone.utc)
        self.sessions[session_id] = session

        return session

    def save(self, session: SessionState) -> None:
        session.last_activity = datetime.now(timezone.utc)
        self.sessions[session.session_id] = session

    def delete(self, session_id: str) -> bool:
        return self.sessions.pop(session_id, None) is not None

    def cleanup_expired(self) -> int:
        now = datetime.now(timezone.utc)

        expired_ids = [
            session_id
            for session_id, session in self.sessions.items()
            if now - session.last_activity > SESSION_LIFETIME
        ]

        for session_id in expired_ids:
            self.sessions.pop(session_id, None)

        return len(expired_ids)


manager = SessionManager()