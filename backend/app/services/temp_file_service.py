from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_LIFETIME = timedelta(minutes=30)


class TempFileService:
    async def save_upload(
        self,
        file: UploadFile,
        session_id: str,
    ) -> str:
        self.cleanup_expired()

        upload_id = str(uuid4())
        safe_name = Path(file.filename or "upload").name

        session_dir = UPLOAD_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        file_path = session_dir / f"{upload_id}__{safe_name}"

        content = await file.read()
        file_path.write_bytes(content)

        return upload_id

    def get_file_path(
        self,
        upload_id: str,
        session_id: str,
    ) -> str | None:
        self.cleanup_expired()

        session_dir = UPLOAD_DIR / session_id

        if not session_dir.exists():
            return None

        matches = list(
            session_dir.glob(f"{upload_id}__*")
        )

        if len(matches) != 1:
            return None

        return str(matches[0])

    def get_filename(
        self,
        upload_id: str,
        session_id: str,
    ) -> str | None:
        file_path = self.get_file_path(
            upload_id=upload_id,
            session_id=session_id,
        )

        if not file_path:
            return None

        filename = Path(file_path).name

        return filename.split("__", 1)[-1]

    def delete_file(
        self,
        upload_id: str,
        session_id: str,
    ) -> bool:
        file_path = self.get_file_path(
            upload_id=upload_id,
            session_id=session_id,
        )

        if not file_path:
            return False

        path = Path(file_path)
        path.unlink(missing_ok=True)

        session_dir = path.parent

        if session_dir.exists() and not any(
            session_dir.iterdir()
        ):
            session_dir.rmdir()

        return True

    def delete_session_uploads(
        self,
        session_id: str,
    ) -> int:
        session_dir = UPLOAD_DIR / session_id

        if not session_dir.exists():
            return 0

        deleted_count = 0

        for file_path in session_dir.iterdir():
            if file_path.is_file():
                file_path.unlink()
                deleted_count += 1

        session_dir.rmdir()

        return deleted_count

    def cleanup_expired(self) -> int:
        now = datetime.now(timezone.utc)
        deleted_count = 0

        for session_dir in UPLOAD_DIR.iterdir():
            if not session_dir.is_dir():
                continue

            for file_path in session_dir.iterdir():
                if not file_path.is_file():
                    continue

                modified_at = datetime.fromtimestamp(
                    file_path.stat().st_mtime,
                    tz=timezone.utc,
                )

                if now - modified_at > UPLOAD_LIFETIME:
                    file_path.unlink()
                    deleted_count += 1

            if not any(session_dir.iterdir()):
                session_dir.rmdir()

        return deleted_count


temp_file_service = TempFileService()