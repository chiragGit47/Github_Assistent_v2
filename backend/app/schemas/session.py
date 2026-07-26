from datetime import datetime, timezone
from typing import Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class SessionState(BaseModel):
    session_id: str
    username: Optional[str] = None
    github_access_token: Optional[str] = None
    current_repo: Optional[str] = None
    messages: list[BaseMessage] = Field(default_factory=list)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_activity: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )