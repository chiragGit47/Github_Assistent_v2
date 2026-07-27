import base64
from pathlib import Path
from typing import Annotated, Any

import httpx
from langchain_core.tools import InjectedToolArg, tool

from app.core.file_validation import (
    validate_file_path,
    validate_file_size,
)
from app.core.zip_validation import read_safe_zip
from app.services.content_service import content_service
from app.services.github_service import github_service
from app.services.temp_file_service import temp_file_service
from app.state.manager import manager


README_FILENAMES = (
    "README.md",
    "README.MD",
    "README",
    "README.txt",
    "Readme.md",
    "readme.md",
)


def get_session_error(session: Any) -> dict | None:
    """
    Validate the current authenticated session.
    """

    if session is None:
        return {
            "success": False,
            "message": (
                "Your session is invalid or expired. "
                "Please log in again."
            ),
            "action": "session_expired",
            "data": None,
            "error": "Session not found",
        }

    if not session.github_access_token:
        return {
            "success": False,
            "message": (
                "GitHub authentication is required. "
                "Please log in again."
            ),
            "action": "authentication_required",
            "data": None,
            "error": "GitHub access token is missing",
        }

    if not session.username:
        return {
            "success": False,
            "message": (
                "Your GitHub username is missing from the session."
            ),
            "action": "user_not_found",
            "data": None,
            "error": "GitHub username is missing",
        }

    return None


async def fetch_readme_from_github(
    access_token: str,
    owner: str,
    repo_name: str,
) -> dict:
    """
    Find and decode a README file from the root of a GitHub repository.
    """

    clean_repo_name = repo_name.strip()

    if not clean_repo_name:
        return {
            "success": False,
            "message": "Repository name is required.",
            "action": "validation_error",
            "data": None,
            "error": "Repository name is empty",
        }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        for filename in README_FILENAMES:
            url = (
                f"https://api.github.com/repos/"
                f"{owner}/{clean_repo_name}/contents/{filename}"
            )

            response = await client.get(
                url,
                headers=headers,
            )

            if response.status_code == 404:
                continue

            if response.status_code == 401:
                return {
                    "success": False,
                    "message": (
                        "Your GitHub authentication has expired. "
                        "Please log in again."
                    ),
                    "action": "authentication_expired",
                    "data": None,
                    "error": "GitHub returned 401",
                }

            if response.status_code == 403:
                return {
                    "success": False,
                    "message": (
                        "GitHub denied access to this repository, "
                        "or the API rate limit was reached."
                    ),
                    "action": "github_access_denied",
                    "data": None,
                    "error": response.text,
                }

            if response.status_code != 200:
                return {
                    "success": False,
                    "message": (
                        f"GitHub could not read '{filename}' "
                        f"from '{clean_repo_name}'."
                    ),
                    "action": "readme_fetch_failed",
                    "data": None,
                    "error": response.text,
                }

            payload = response.json()

            encoded_content = payload.get("content", "")
            encoding = payload.get("encoding")

            if not encoded_content:
                return {
                    "success": False,
                    "message": (
                        f"The README file in "
                        f"'{clean_repo_name}' is empty."
                    ),
                    "action": "readme_empty",
                    "data": None,
                    "error": "README content is empty",
                }

            if encoding != "base64":
                return {
                    "success": False,
                    "message": (
                        "The README uses an unsupported encoding."
                    ),
                    "action": "unsupported_encoding",
                    "data": None,
                    "error": f"Encoding: {encoding}",
                }

            try:
                readme_content = base64.b64decode(
                    encoded_content
                ).decode(
                    "utf-8",
                    errors="replace",
                )
            except Exception as exc:
                return {
                    "success": False,
                    "message": (
                        "The README was found but could not be decoded."
                    ),
                    "action": "readme_decode_failed",
                    "data": None,
                    "error": str(exc),
                }

            return {
                "success": True,
                "message": "README found successfully.",
                "action": "readme_found",
                "data": {
                    "repo_name": clean_repo_name,
                    "owner": owner,
                    "filename": filename,
                    "content": readme_content,
                    "html_url": payload.get("html_url"),
                    "download_url": payload.get("download_url"),
                    "size": payload.get("size"),
                },
                "error": None,
            }

    return {
        "success": False,
        "message": (
            f"No README file was found in the root of "
            f"'{clean_repo_name}'."
        ),
        "action": "readme_not_found",
        "data": {
            "repo_name": clean_repo_name,
            "checked_filenames": list(README_FILENAMES),
        },
        "error": "README not found",
    }


@tool
async def fetch_repositories(
    session_id: Annotated[str, InjectedToolArg],
) -> dict:
    """
    Fetch repositories accessible to the authenticated GitHub user.
    """

    session = manager.get(session_id)
    session_error = get_session_error(session)

    if session_error:
        return session_error

    try:
        repositories = await github_service.list_repositories(
            access_token=session.github_access_token,
        )

        public_count = sum(
            1
            for repository in repositories
            if not repository.get("private", False)
        )

        private_count = sum(
            1
            for repository in repositories
            if repository.get("private", False)
        )

        return {
            "success": True,
            "message": "Repositories fetched successfully.",
            "action": "repositories_fetched",
            "data": {
                "count": len(repositories),
                "public_count": public_count,
                "private_count": private_count,
                "repositories": [
                    {
                        "name": repository.get("name"),
                        "private": repository.get(
                            "private",
                            False,
                        ),
                        "url": repository.get("html_url"),
                        "owner": (
                            repository.get(
                                "owner",
                                {},
                            ).get("login")
                            if isinstance(
                                repository.get("owner"),
                                dict,
                            )
                            else None
                        ),
                    }
                    for repository in repositories
                ],
            },
            "error": None,
        }

    except Exception as exc:
        return {
            "success": False,
            "message": (
                "GitHub repositories could not be fetched."
            ),
            "action": "fetch_repositories_error",
            "data": None,
            "error": str(exc),
        }


@tool
async def create_repository(
    repo_name: str,
    session_id: Annotated[str, InjectedToolArg],
    private: bool = False,
) -> dict:
    """
    Create a new GitHub repository.
    """

    session = manager.get(session_id)
    session_error = get_session_error(session)

    if session_error:
        return session_error

    clean_repo_name = repo_name.strip()

    if not clean_repo_name:
        return {
            "success": False,
            "message": "Repository name is required.",
            "action": "validation_error",
            "data": None,
            "error": "Repository name is empty",
        }

    try:
        repository = await github_service.create_repository(
            access_token=session.github_access_token,
            repo_name=clean_repo_name,
            private=private,
        )

        session.current_repo = repository["name"]
        manager.save(session)

        return {
            "success": True,
            "message": "Repository created successfully.",
            "action": "repository_created",
            "data": {
                "name": repository["name"],
                "private": repository["private"],
                "url": repository["html_url"],
            },
            "error": None,
        }

    except Exception as exc:
        return {
            "success": False,
            "message": "Repository creation failed.",
            "action": "create_repository_error",
            "data": None,
            "error": str(exc),
        }


@tool
async def upload_single_file(
    repo_name: str,
    upload_id: str,
    destination_path: str,
    session_id: Annotated[str, InjectedToolArg],
    commit_message: str = (
        "Upload file using GitHub Assistant"
    ),
) -> dict:
    """
    Upload one prepared temporary file to a GitHub repository.

    destination_path is the path inside the repository,
    for example app/main.py.
    """

    session = manager.get(session_id)
    session_error = get_session_error(session)

    if session_error:
        return session_error

    local_path = temp_file_service.get_file_path(
        upload_id=upload_id,
        session_id=session_id,
    )

    if local_path is None:
        return {
            "success": False,
            "message": (
                "The prepared upload was not found or has expired."
            ),
            "action": "upload_not_found",
            "data": None,
            "error": "Upload was not found",
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
            "action": "file_uploaded",
            "data": {
                "repository": repo_name.strip(),
                "file": {
                    "name": result["content"]["name"],
                    "path": result["content"]["path"],
                    "url": result["content"]["html_url"],
                },
            },
            "error": None,
        }

    except Exception as exc:
        return {
            "success": False,
            "message": "File upload failed.",
            "action": "upload_single_file_error",
            "data": None,
            "error": str(exc),
        }

    finally:
        temp_file_service.delete_file(
            upload_id=upload_id,
            session_id=session_id,
        )


@tool
async def upload_project_zip(
    repo_name: str,
    upload_id: str,
    session_id: Annotated[str, InjectedToolArg],
    commit_message: str = (
        "Upload project using GitHub Assistant"
    ),
) -> dict:
    """
    Upload a prepared ZIP project to a GitHub repository.
    """

    session = manager.get(session_id)
    session_error = get_session_error(session)

    if session_error:
        return session_error

    local_path = temp_file_service.get_file_path(
        upload_id=upload_id,
        session_id=session_id,
    )

    if local_path is None:
        return {
            "success": False,
            "message": (
                "The ZIP upload was not found or has expired."
            ),
            "action": "upload_not_found",
            "data": None,
            "error": "ZIP upload was not found",
        }

    try:
        zip_content = Path(local_path).read_bytes()

        project_files = read_safe_zip(
            zip_content
        )

        result = await github_service.upload_files_batch(
            access_token=session.github_access_token,
            owner=session.username,
            repo_name=repo_name.strip(),
            files=project_files,
            commit_message=commit_message.strip(),
        )

        session.current_repo = repo_name.strip()
        manager.save(session)

        temp_file_service.delete_file(
            upload_id=upload_id,
            session_id=session_id,
        )

        return {
            "success": True,
            "message": "Project uploaded successfully.",
            "action": "project_uploaded",
            "data": {
                "repository": repo_name.strip(),
                **result,
            },
            "error": None,
        }

    except Exception as exc:
        return {
            "success": False,
            "message": "Project upload failed.",
            "action": "upload_project_zip_error",
            "data": {
                "upload_id": upload_id,
            },
            "error": str(exc),
        }


@tool
async def read_repository_readme(
    repo_name: str,
    session_id: Annotated[str, InjectedToolArg],
) -> dict:
    """
    Find and return README content from an authenticated user's
    GitHub repository.
    """

    session = manager.get(session_id)
    session_error = get_session_error(session)

    if session_error:
        return session_error

    result = await fetch_readme_from_github(
        access_token=session.github_access_token,
        owner=session.username,
        repo_name=repo_name,
    )

    if result.get("success"):
        session.current_repo = repo_name.strip()
        manager.save(session)

    return result


@tool
async def generate_linkedin_post(
    repo_name: str,
    session_id: Annotated[str, InjectedToolArg],
) -> dict:
    """
    Generate a LinkedIn post from a repository README.
    """

    session = manager.get(session_id)
    session_error = get_session_error(session)

    if session_error:
        return session_error

    try:
        readme_result = await fetch_readme_from_github(
            access_token=session.github_access_token,
            owner=session.username,
            repo_name=repo_name,
        )

        if not readme_result.get("success"):
            return readme_result

        readme_content = readme_result["data"]["content"]
        clean_repo_name = repo_name.strip()

        repo_url = (
            f"https://github.com/"
            f"{session.username}/{clean_repo_name}"
        )

        linkedin_post = await content_service.generate_linkedin_post(
            repo_name=clean_repo_name,
            readme_content=readme_content,
            repo_url=repo_url,
        )

        session.current_repo = clean_repo_name
        manager.save(session)

        return {
            "success": True,
            "message": "LinkedIn post generated successfully.",
            "action": "linkedin_post_generated",
            "linkedin_post": linkedin_post,
            "data": {
                "repo_name": clean_repo_name,
                "repo_url": repo_url,
                "readme_filename": (
                    readme_result["data"]["filename"]
                ),
            },
            "error": None,
        }

    except Exception as exc:
        return {
            "success": False,
            "message": (
                "The LinkedIn post could not be generated."
            ),
            "action": "generate_linkedin_post_error",
            "data": None,
            "error": str(exc),
        }


@tool
async def generate_resume_points(
    repo_name: str,
    session_id: Annotated[str, InjectedToolArg],
) -> dict:
    """
    Generate resume bullet points from a repository README.
    """

    session = manager.get(session_id)
    session_error = get_session_error(session)

    if session_error:
        return session_error

    try:
        readme_result = await fetch_readme_from_github(
            access_token=session.github_access_token,
            owner=session.username,
            repo_name=repo_name,
        )

        if not readme_result.get("success"):
            return readme_result

        readme_content = (
            readme_result["data"]["content"]
        )

        clean_repo_name = repo_name.strip()

        repo_url = (
            f"https://github.com/"
            f"{session.username}/{clean_repo_name}"
        )

        points = (
            await content_service.generate_resume_points(
                repo_name=clean_repo_name,
                readme_content=readme_content,
                repo_url=repo_url,
            )
        )

        session.current_repo = clean_repo_name
        manager.save(session)

        return {
            "success": True,
            "message": (
                "Resume points generated successfully."
            ),
            "action": "resume_points_generated",
            "resume_points": points,
            "data": {
                "repo_name": clean_repo_name,
                "repo_url": repo_url,
                "readme_filename": (
                    readme_result["data"]["filename"]
                ),
            },
            "error": None,
        }

    except Exception as exc:
        return {
            "success": False,
            "message": (
                "The resume points could not be generated."
            ),
            "action": "generate_resume_points_error",
            "data": None,
            "error": str(exc),
        }