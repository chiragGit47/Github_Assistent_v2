from fastapi import APIRouter
from pydantic import BaseModel

from app.api.dependencies import get_valid_session
from app.services.content_service import content_service
from app.services.github_service import github_service


router = APIRouter(
    prefix="/content",
    tags=["Content"],
)


class RepositoryContentRequest(BaseModel):
    session_id: str
    repo_name: str
    readme_path: str = "README.md"


@router.post("/linkedin-post")
async def create_linkedin_post(
    request: RepositoryContentRequest,
):
    session = get_valid_session(request.session_id)

    readme = await github_service.read_file(
        access_token=session.github_access_token,
        owner=session.username,
        repo_name=request.repo_name.strip(),
        file_path=request.readme_path.strip(),
    )

    post = await content_service.generate_linkedin_post(
        readme["content"]
    )

    return {
        "success": True,
        "repo_name": request.repo_name,
        "linkedin_post": post,
    }


@router.post("/resume-points")
async def create_resume_points(
    request: RepositoryContentRequest,
):
    session = get_valid_session(request.session_id)

    readme = await github_service.read_file(
        access_token=session.github_access_token,
        owner=session.username,
        repo_name=request.repo_name.strip(),
        file_path=request.readme_path.strip(),
    )

    points = await content_service.generate_resume_points(
        readme["content"]
    )

    return {
        "success": True,
        "repo_name": request.repo_name,
        "resume_points": points,
    }