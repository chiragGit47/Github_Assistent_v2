from fastapi import HTTPException

from app.schemas.session import SessionState
from app.state.manager import manager


def get_valid_session(session_id: str) -> SessionState:
    session = manager.get(session_id)

    if not session:
        raise HTTPException(
            status_code=401,
            detail="Session is invalid or expired.",
        )

    if not session.github_access_token:
        raise HTTPException(
            status_code=401,
            detail="GitHub access token is missing.",
        )

    return session