import pytest
from fastapi import HTTPException

from app.core.file_validation import (
    validate_file_path,
    validate_file_size,
)


def test_valid_file_path():
    result = validate_file_path("app/main.py")

    assert result == "app/main.py"


def test_unsafe_file_path():
    with pytest.raises(HTTPException):
        validate_file_path("../../secret.txt")


def test_empty_file():
    with pytest.raises(HTTPException):
        validate_file_size(b"")