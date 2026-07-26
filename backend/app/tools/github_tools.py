from pathlib import Path

from langchain_core.tools import tool

from app.core.exceptions import GitHubAPIError
from app.core.file_validation import (
    validate_file_path,
    validate_file_size,
)
from app.core.zip_validation import read_safe_zip
from app.services.content_service import content_service
from app.services.github_service import github_service
from app.services.temp_file_service import temp_file_service
from app.state.manager import manager
from typing import Annotated

from langchain_core.tools import InjectedToolArg, tool


@tool
async def fetch_repositories(session_id: Annotated[str, InjectedToolArg],) -> dict:
    """Fetch repositories accessible to the authenticated GitHub user."""

    session = manager.get(session_id)

    if session is None:
        return {
            "success": False,
            "error": "Session is invalid or expired.",
        }

    if not session.github_access_token:
        return {
            "success": False,
            "error": "GitHub access token is missing.",
        }

    repositories = await github_service.list_repositories(
        access_token=session.github_access_token,
    )

    return {
        "success": True,
        "count": len(repositories),
        "repositories": [
            {
                "name": repository.get("name"),
                "private": repository.get("private", False),
                "url": repository.get("html_url"),
            }
            for repository in repositories
        ],
    }


@tool
async def create_repository(
    session_id: Annotated[str, InjectedToolArg],
    repo_name: str,
    private: bool = False,
) -> dict:
    """Create a new GitHub repository."""

    session = manager.get(session_id)

    if session is None:
        return {
            "success": False,
            "error": "Session is invalid or expired.",
        }

    if not repo_name.strip():
        return {
            "success": False,
            "error": "Repository name is required.",
        }

    repository = await github_service.create_repository(
        access_token=session.github_access_token,
        repo_name=repo_name.strip(),
        private=private,
    )

    session.current_repo = repository["name"]
    manager.save(session)

    return {
        "success": True,
        "message": "Repository created successfully.",
        "repository": {
            "name": repository["name"],
            "private": repository["private"],
            "url": repository["html_url"],
        },
    }


@tool
async def upload_single_file(
    session_id: Annotated[str, InjectedToolArg],
    repo_name: str,
    upload_id: str,
    destination_path: str,
    commit_message: str = "Upload file using GitHub Assistant",
) -> dict:
    """
    Upload one prepared temporary file to a GitHub repository.

    destination_path is the path inside the repository,
    for example app/main.py.
    """

    session = manager.get(session_id)

    if session is None:
        return {
            "success": False,
            "error": "Session is invalid or expired.",
        }

    local_path = temp_file_service.get_file_path(
        upload_id=upload_id,
        session_id=session_id,
    )

    if local_path is None:
        return {
            "success": False,
            "error": "Upload was not found or has expired.",
        }

    try:
        file_content = Path(local_path).read_bytes()

        validate_file_size(file_content)

        safe_destination = validate_file_path(
            destination_path
        )

        result = await github_service.upload_file(
            access_token=session.github_access_token,
            owner=session.username,
            repo_name=repo_name.strip(),
            file_path=safe_destination,
            file_content=file_content,
            commit_message=commit_message.strip(),
        )

        session.current_repo = repo_name.strip()
        manager.save(session)

        return {
            "success": True,
            "message": "File uploaded successfully.",
            "repository": repo_name.strip(),
            "file": {
                "name": result["content"]["name"],
                "path": result["content"]["path"],
                "url": result["content"]["html_url"],
            },
        }

    finally:
        temp_file_service.delete_file(
            upload_id=upload_id,
            session_id=session_id,
        )


@tool
async def upload_project_zip(
    session_id: Annotated[str, InjectedToolArg],
    repo_name: str,
    upload_id: str,
    commit_message: str = "Upload project using GitHub Assistant",
) -> dict:
    """Upload a prepared ZIP project to a GitHub repository."""

    session = manager.get(session_id)

    if session is None:
        return {
            "success": False,
            "error": "Session is invalid or expired.",
        }

    local_path = temp_file_service.get_file_path(
        upload_id=upload_id,
        session_id=session_id,
    )

    if local_path is None:
        return {
            "success": False,
            "error": "ZIP upload was not found or has expired.",
        }

    try:
        zip_content = Path(local_path).read_bytes()
        project_files = read_safe_zip(zip_content)

        result = await github_service.upload_files_batch(
            access_token=session.github_access_token,
            owner=session.username,
            repo_name=repo_name.strip(),
            files=project_files,
            commit_message=commit_message.strip(),
        )

        session.current_repo = repo_name.strip()
        manager.save(session)

        # Delete only after successful upload.
        temp_file_service.delete_file(
            upload_id=upload_id,
            session_id=session_id,
        )

        return {
            "success": True,
            "message": "Project uploaded successfully.",
            "repository": repo_name.strip(),
            **result,
        }

    except Exception as error:
        return {
            "success": False,
            "error": "Project upload failed.",
            "details": str(error),
            "upload_id": upload_id,
        }


@tool
async def generate_linkedin_post(
    session_id: Annotated[str, InjectedToolArg],
    repo_name: str,
) -> dict:
    """Generate a LinkedIn post from a repository README file."""

    session = manager.get(session_id)

    if session is None:
        return {
            "success": False,
            "error": "Session is invalid or expired.",
        }

    readme = await github_service.read_file(
        access_token=session.github_access_token,
        owner=session.username,
        repo_name=repo_name.strip(),
        file_path="README.md",
    )

    post = await content_service.generate_linkedin_post(
        readme["content"]
    )

    session.current_repo = repo_name.strip()
    manager.save(session)

    return {
        "success": True,
        "repo_name": repo_name.strip(),
        "linkedin_post": post,
    }


@tool
async def generate_resume_points(
    session_id: Annotated[str, InjectedToolArg],
    repo_name: str,
) -> dict:
    """Generate resume bullet points from a repository README file."""

    session = manager.get(session_id)

    if session is None:
        return {
            "success": False,
            "error": "Session is invalid or expired.",
        }

    readme = await github_service.read_file(
        access_token=session.github_access_token,
        owner=session.username,
        repo_name=repo_name.strip(),
        file_path="README.md",
    )

    points = await content_service.generate_resume_points(
        readme["content"]
    )

    session.current_repo = repo_name.strip()
    manager.save(session)

    return {
        "success": True,
        "repo_name": repo_name.strip(),
        "resume_points": points,
    }