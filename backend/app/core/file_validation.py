from pathlib import PurePosixPath

from fastapi import HTTPException


MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_file_path(file_path: str) -> str:
    cleaned_path = file_path.strip().replace("\\", "/")
    path = PurePosixPath(cleaned_path)

    if not cleaned_path:
        raise HTTPException(
            status_code=400,
            detail="File path is required.",
        )

    if path.is_absolute() or ".." in path.parts:
        raise HTTPException(
            status_code=400,
            detail="Invalid file path.",
        )

    return str(path)


def validate_file_size(file_content: bytes) -> None:
    if not file_content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File is larger than 5 MB.",
        )