"""本地文件系统存储。抽象为函数集，后续可替换为 S3 兼容后端（StorageBackend）。"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from liberastra.core.config import get_settings
from liberastra.models import Asset

_MIME_BY_EXT = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".srt": "application/x-subrip",
    ".vtt": "text/vtt",
    ".txt": "text/plain",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".mp4": "video/mp4",
}


def data_dir() -> Path:
    path = get_settings().data_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve(rel_path: str) -> Path:
    """相对数据目录的路径解析为绝对路径，并阻止目录逃逸。"""
    root = data_dir().resolve()
    path = (root / rel_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"非法路径: {rel_path}")
    return path


def save_bytes(content: bytes, rel_path: str) -> Path:
    path = resolve(rel_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def save_upload(filename: str, content: bytes) -> str:
    """保存上传文件到 uploads/，返回相对路径。"""
    safe_name = Path(filename).name or "upload.bin"
    rel = f"uploads/{uuid.uuid4().hex[:12]}_{safe_name}"
    save_bytes(content, rel)
    return rel


def save_ref_audio(filename: str, content: bytes) -> str:
    safe_name = Path(filename).name or "ref.wav"
    rel = f"voices/{uuid.uuid4().hex[:12]}_{safe_name}"
    save_bytes(content, rel)
    return rel


def create_asset(
    db: Session,
    *,
    kind: str,
    rel_path: str,
    job_id: str | None = None,
    owner_id: int,
    meta: dict | None = None,
    hidden: bool = False,
) -> Asset:
    path = resolve(rel_path)
    asset = Asset(
        kind=kind,
        path=rel_path,
        mime=_MIME_BY_EXT.get(path.suffix.lower()),
        size=path.stat().st_size if path.exists() else 0,
        job_id=job_id,
        meta=meta or {},
        hidden=hidden,
        owner_id=owner_id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset
