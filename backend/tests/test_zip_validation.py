from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi import HTTPException

from app.core.zip_validation import read_safe_zip


def create_zip(files: dict[str, bytes]) -> bytes:
    buffer = BytesIO()

    with ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)

    return buffer.getvalue()


def test_valid_zip():
    zip_content = create_zip({
        "app/main.py": b"print('hello')",
        "README.md": b"# Project",
    })

    files = read_safe_zip(zip_content)

    assert len(files) == 2


def test_unsafe_zip_path():
    zip_content = create_zip({
        "../../secret.txt": b"secret",
    })

    with pytest.raises(HTTPException):
        read_safe_zip(zip_content)