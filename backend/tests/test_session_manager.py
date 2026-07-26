from app.schemas.session import SessionState
from app.state.manager import SessionManager


def test_create_and_get_session():
    manager = SessionManager()

    session = SessionState(
        session_id="test-session",
        username="chirag",
        github_access_token="token",
    )

    manager.create(session)

    result = manager.get("test-session")

    assert result is not None
    assert result.username == "chirag"


def test_delete_session():
    manager = SessionManager()

    session = SessionState(
        session_id="test-session",
    )

    manager.create(session)

    deleted = manager.delete("test-session")

    assert deleted is True
    assert manager.get("test-session") is None