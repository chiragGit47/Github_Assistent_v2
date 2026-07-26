import re

from fastapi import HTTPException


REPOSITORY_PATTERN = re.compile(
    r"^[A-Za-z0-9._-]{1,100}$"
)


def validate_repository_name(
    repo_name: str,
) -> str:
    cleaned_name = repo_name.strip()

    if not REPOSITORY_PATTERN.fullmatch(
        cleaned_name
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid repository name.",
        )

    return cleaned_name