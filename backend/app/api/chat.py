from fastapi import APIRouter

from app.agents.github_agent import github_agent
from app.api.dependencies import get_valid_session
from app.schemas.chat import ChatRequest, ChatResponse


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    response_model=ChatResponse,
)
async def chat(request: ChatRequest):
    get_valid_session(request.session_id)

    result = await github_agent.chat(
        session_id=request.session_id,
        user_message=request.message,
    )

    return ChatResponse(**result)