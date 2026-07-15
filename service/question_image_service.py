from __future__ import annotations

from utils.messages import Messages

import os
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.datastructures import FileStorage

from service.exceptions import ValidationError

_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}


class QuestionImageService:
    def __init__(self, storage_dir: str | None = None):
        self.storage_dir = storage_dir or current_app.config.get(
            "QUESTION_IMAGE_STORAGE_DIR"
        )
        self.max_bytes = int(current_app.config.get("QUESTION_IMAGE_MAX_BYTES", 5 * 1024 * 1024))

    def save_question_image(
        self,
        *,
        image_file: FileStorage,
        workspace_id: int,
        owner_user_id: int,
    ) -> str:
        if not image_file:
            raise ValidationError(Messages.IMAGE_FILE_IS_REQUIRED)

        filename = image_file.filename or ""
        extension = Path(filename).suffix.lower()
        mimetype = (image_file.mimetype or "").lower()

        if extension not in _ALLOWED_EXTENSIONS:
            raise ValidationError(Messages.UNSUPPORTED_IMAGE_EXTENSION_ALLOWED_JPG_JPEG_PNG_WEBP)
        if mimetype not in _ALLOWED_MIME_TYPES:
            raise ValidationError(Messages.INVALID_FILE_TYPE_ONLY_IMAGE_FILES_ARE_ALLOWED)

        size = self._resolve_file_size(image_file)
        if size <= 0:
            raise ValidationError(Messages.UPLOADED_IMAGE_IS_EMPTY)
        if size > self.max_bytes:
            max_mb = self.max_bytes / (1024 * 1024)
            raise ValidationError(Messages.IMAGE_IS_TOO_LARGE.format(max_mb=max_mb))

        rel_dir = Path(str(workspace_id)) / str(owner_user_id)
        target_dir = Path(self.storage_dir) / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        unique_name = f"{uuid.uuid4().hex}{extension}"
        target_path = target_dir / unique_name
        image_file.save(target_path)

        return f"questions/{rel_dir.as_posix()}/{unique_name}"

    def upload_image(
        self,
        *,
        image_file: FileStorage,
        workspace_id: int,
        owner_user_id: int,
    ) -> dict:
        """Standalone upload — returns path metadata for use in question/test APIs."""
        image_path = self.save_question_image(
            image_file=image_file,
            workspace_id=workspace_id,
            owner_user_id=owner_user_id,
        )
        file_name = Path(image_path).name
        return {
            "success": True,
            "image_path": image_path,
            "file_name": file_name,
            "image_url": self.build_public_url(image_path),
        }

    def delete_if_local(self, image_path: str | None) -> None:
        if not image_path:
            return
        if not image_path.startswith("questions/"):
            return

        full_path = Path(self.storage_dir).parent / image_path
        try:
            if full_path.exists():
                full_path.unlink()
        except OSError:
            # Best-effort cleanup; shouldn't block question updates.
            return

    def build_public_url(self, image_path: str | None) -> str | None:
        if not image_path:
            return None
        base_url = current_app.config.get("API_URL", "").rstrip("/")
        return f"{base_url}/uploads/{image_path}"

    def _resolve_file_size(self, image_file: FileStorage) -> int:
        stream = image_file.stream
        current = stream.tell()
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(current, os.SEEK_SET)
        return int(size)
