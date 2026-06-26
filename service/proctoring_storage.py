"""
Storage abstraction for proctoring evidence (screenshots, video clips).

Implementations must not hardcode a cloud provider; swap backend via config.
"""
from __future__ import annotations

import base64
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from flask import current_app


class ProctoringStorageBackend(ABC):
    @abstractmethod
    def store(
        self,
        *,
        workspace_id: int,
        session_id: int,
        filename: str,
        data: bytes,
        content_type: str,
    ) -> str:
        """Persist bytes and return an opaque storage reference (URI or key)."""


class LocalProctoringStorageBackend(ProctoringStorageBackend):
    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "uploads", "proctoring"
        )

    def store(
        self,
        *,
        workspace_id: int,
        session_id: int,
        filename: str,
        data: bytes,
        content_type: str,
    ) -> str:
        rel_dir = Path(str(workspace_id)) / str(session_id)
        target_dir = Path(self.base_dir) / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_name = filename or f"{uuid.uuid4().hex}.bin"
        path = target_dir / safe_name
        path.write_bytes(data)
        return f"local://proctoring/{rel_dir.as_posix()}/{safe_name}"


class ProctoringStorageService:
    def __init__(self, backend: ProctoringStorageBackend | None = None):
        self._backend = backend

    @property
    def backend(self) -> ProctoringStorageBackend:
        if self._backend is None:
            root = current_app.config.get(
                "PROCTORING_STORAGE_DIR",
                os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "uploads", "proctoring"
                ),
            )
            self._backend = LocalProctoringStorageBackend(base_dir=root)
        return self._backend

    def store_screenshot(
        self,
        *,
        workspace_id: int,
        session_id: int,
        image_base64: str,
        content_type: str = "image/png",
    ) -> str:
        raw = image_base64.split(",", 1)[-1]
        data = base64.b64decode(raw)
        ext = "png" if "png" in content_type else "jpg"
        return self.backend.store(
            workspace_id=workspace_id,
            session_id=session_id,
            filename=f"screenshot_{uuid.uuid4().hex}.{ext}",
            data=data,
            content_type=content_type,
        )

    def store_video_clip(
        self,
        *,
        workspace_id: int,
        session_id: int,
        video_base64: str,
        content_type: str = "video/webm",
    ) -> str:
        raw = video_base64.split(",", 1)[-1]
        data = base64.b64decode(raw)
        return self.backend.store(
            workspace_id=workspace_id,
            session_id=session_id,
            filename=f"clip_{uuid.uuid4().hex}.webm",
            data=data,
            content_type=content_type,
        )
