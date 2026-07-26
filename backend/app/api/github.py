from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.dependencies import get_valid_session
from app.schemas.session import SessionState
from app.services.github_service import github_service
from app.state.manager import manager
from fastapi import UploadFile, File, Form

from app.services.temp_file_service import temp_file_service


from app.core.file_validation import (
    validate_file_path,
    validate_file_size,
)
from app.core.zip_validation import read_safe_zip


router = APIRouter(
    prefix="/github",
    tags=["GitHub"],
)


class CreateRepositoryRequest(BaseModel):
    session_id: str
    repo_name: str = Field(
        min_length=1,
        max_length=100,
    )
    private: bool = False


@router.get("/repos/{session_id}")
async def fetch_repositories(
    session: SessionState = Depends(get_valid_session),
):
    repositories = await github_service.list_repositories(
        session.github_access_token
    )

    return {
        "success": True,
        "count": len(repositories),
        "repositories": [
            {
                "name": repo["name"],
                "private": repo["private"],
                "url": repo["html_url"],
            }
            for repo in repositories
        ],
    }


@router.post("/repos")
async def create_repository(
    request: CreateRepositoryRequest,
):
    session = get_valid_session(request.session_id)

    repository = await github_service.create_repository(
        access_token=session.github_access_token,
        repo_name=request.repo_name.strip(),
        private=request.private,
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


@router.post("/upload-file")
async def upload_file(
    session_id: str = Form(...),
    repo_name: str = Form(...),
    file_path: str = Form(...),
    commit_message: str = Form(
        "Upload file using GitHub Assistant"
    ),
    file: UploadFile = File(...),
):
    session = get_valid_session(session_id)

    file_content = await file.read()

    validate_file_size(file_content)
    safe_file_path = validate_file_path(file_path)

    result = await github_service.upload_file(
        access_token=session.github_access_token,
        owner=session.username,
        repo_name=repo_name.strip(),
        file_path=safe_file_path,
        file_content=file_content,
        commit_message=commit_message.strip(),
    )

    session.current_repo = repo_name.strip()
    manager.save(session)

    return {
        "success": True,
        "message": "File uploaded successfully.",
        "file": {
            "name": result["content"]["name"],
            "path": result["content"]["path"],
            "url": result["content"]["html_url"],
        },
    }

@router.post("/upload-project")
async def upload_project(
    session_id: str = Form(...),
    repo_name: str = Form(...),
    commit_message: str = Form(
        "Upload project using GitHub Assistant"
    ),
    zip_file: UploadFile = File(...),
):
    session = get_valid_session(session_id)

    zip_content = await zip_file.read()
    project_files = read_safe_zip(zip_content)

    uploaded_files = []

    for file_path, file_content in project_files:
        result = await github_service.upload_file(
            access_token=session.github_access_token,
            owner=session.username,
            repo_name=repo_name.strip(),
            file_path=file_path,
            file_content=file_content,
            commit_message=commit_message.strip(),
        )

        uploaded_files.append(
            {
                "name": result["content"]["name"],
                "path": result["content"]["path"],
                "url": result["content"]["html_url"],
            }
        )

    session.current_repo = repo_name.strip()
    manager.save(session)

    return {
        "success": True,
        "message": "Project uploaded successfully.",
        "uploaded_count": len(uploaded_files),
        "files": uploaded_files,
    }


@router.get("/read-file/{session_id}")
async def read_repository_file(
    session_id: str,
    repo_name: str,
    file_path: str,
):
    session = get_valid_session(session_id)

    result = await github_service.read_file(
        access_token=session.github_access_token,
        owner=session.username,
        repo_name=repo_name.strip(),
        file_path=file_path.strip(),
    )

    session.current_repo = repo_name.strip()
    manager.save(session)

    return {
        "success": True,
        "file": result,
    }



@router.post("/prepare-upload")
async def prepare_upload(
    session_id: str = Form(...),
    file: UploadFile = File(...),
):
    get_valid_session(session_id)

    upload_id = await temp_file_service.save_upload(
        file=file,
        session_id=session_id,
    )

    return {
        "success": True,
        "message": "File saved temporarily.",
        "upload_id": upload_id,
        "filename": file.filename,
    }