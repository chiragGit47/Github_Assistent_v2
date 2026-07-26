from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.content import router as content_router
from app.api.github import router as github_router
from app.core.exceptions import GitHubAPIError
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="GitHub Assistant API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(github_router)
app.include_router(content_router)
app.include_router(chat_router)


@app.exception_handler(GitHubAPIError)
async def github_error_handler(
    request: Request,
    error: GitHubAPIError,
):
    return JSONResponse(
        status_code=error.status_code,
        content={
            "success": False,
            "message": error.message,
            "details": error.details,
        },
    )


@app.get("/health")
async def health():
    return {
        "success": True,
        "message": "GitHub Assistant backend is running.",
    }