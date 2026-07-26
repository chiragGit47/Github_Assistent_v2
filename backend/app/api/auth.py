from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException 
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from app.core.config import settings
from app.schemas.session import SessionState
from app.state.manager import manager
from app.services.temp_file_service import temp_file_service


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.get("/login")
async def github_login():
    github_auth_url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.github_client_id}"
        "&scope=repo read:user"
    )

    return RedirectResponse(github_auth_url)


@router.get("/callback")
async def github_callback(code: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={
                "Accept": "application/json",
            },
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
        )

        token_data = token_response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="GitHub authentication failed.",
            )

        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )

        if user_response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail="Could not fetch GitHub user.",
            )

        user_data = user_response.json()

    session_id = str(uuid4())

    session = SessionState(
        session_id=session_id,
        username=user_data["login"],
        github_access_token=access_token,
    )

    manager.create(session)

    redirect_url = (
        f"{settings.frontend_url}"
        f"?session_id={session_id}"
        f"&username={user_data['login']}"
    )

    return RedirectResponse(redirect_url)


class LogoutRequest(BaseModel):
    session_id: str


@router.post("/logout")
async def logout(request: LogoutRequest):
    temp_file_service.delete_session_uploads(
        request.session_id
    )

    deleted = manager.delete(request.session_id)

    return {
        "success": deleted,
        "message": (
            "Session and temporary files deleted."
            if deleted
            else "Session not found."
        ),
    }