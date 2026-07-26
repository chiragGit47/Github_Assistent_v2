from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException


MAX_ZIP_SIZE = 20 * 1024 * 1024
MAX_FILES = 150
MAX_EXTRACTED_SIZE = 50 * 1024 * 1024

IGNORED_PARTS = {
    "venv",
    ".venv",
    "node_modules",
    "__pycache__",
    ".git",
    ".DS_Store",
}


def read_safe_zip(
    zip_content: bytes,
) -> list[tuple[str, bytes]]:
    if not zip_content:
        raise HTTPException(
            status_code=400,
            detail="ZIP file is empty.",
        )

    if len(zip_content) > MAX_ZIP_SIZE:
        raise HTTPException(
            status_code=413,
            detail="ZIP file is larger than 20 MB.",
        )

    try:
        with ZipFile(BytesIO(zip_content)) as archive:
            files: list[tuple[str, bytes]] = []
            total_extracted_size = 0

            for item in archive.infolist():
                if item.is_dir():
                    continue

                total_extracted_size += item.file_size

                if total_extracted_size > MAX_EXTRACTED_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="Extracted ZIP content is too large.",
                    )

                is_symlink = (
                    (item.external_attr >> 16) & 0o170000
                ) == 0o120000

                if is_symlink:
                    continue

                path = PurePosixPath(item.filename)

                if path.is_absolute() or ".." in path.parts:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unsafe ZIP path: {item.filename}",
                    )

                if any(
                    part in IGNORED_PARTS
                    for part in path.parts
                ):
                    continue

                files.append(
                    (
                        str(path),
                        archive.read(item),
                    )
                )

                if len(files) > MAX_FILES:
                    raise HTTPException(
                        status_code=400,
                        detail="ZIP contains too many files.",
                    )

            if not files:
                raise HTTPException(
                    status_code=400,
                    detail="ZIP contains no valid files.",
                )

            return files

    except BadZipFile:
        raise HTTPException(
            status_code=400,
            detail="Invalid ZIP file.",
        )