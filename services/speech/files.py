"""上传文件的分块存储和生命周期管理。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO

FILE_ID_RE = re.compile(r"^f_[0-9a-f]{32}$")
_SUFFIX_RE = re.compile(r"^[a-z0-9.]{1,16}$")


class FileStoreError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class FileRecord:
    file_id: str
    filename: str
    suffix: str
    size: int
    sha256: str
    created_at: datetime
    expires_at: datetime | None
    path: Path

    def public(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "size": self.size,
            "sha256": self.sha256,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(0, value)


def _default_root() -> Path:
    raw = os.getenv("LIBER_SPEECH_FILES_DIR", "").strip()
    if raw:
        return Path(raw)
    results = Path(os.getenv("LIBER_SPEECH_RESULTS_DIR", "results"))
    return results.parent / "files"


def _parse_datetime(raw: str) -> datetime:
    value = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class FileStore:
    def __init__(
        self,
        root: Path | None = None,
        *,
        max_bytes: int | None = None,
        ttl_seconds: int | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        self.root = Path(root) if root is not None else _default_root()
        self.max_bytes = (
            _env_int("LIBER_SPEECH_MAX_UPLOAD_BYTES", 0)
            if max_bytes is None
            else max(0, max_bytes)
        )
        self.ttl_seconds = (
            _env_int("LIBER_SPEECH_FILE_TTL_SECONDS", 86400)
            if ttl_seconds is None
            else max(0, ttl_seconds)
        )
        self.chunk_size = max(1, chunk_size)

    def _meta_path(self, file_id: str) -> Path:
        return self.root / f"{file_id}.json"

    @staticmethod
    def _suffix(filename: str) -> tuple[str, str]:
        original = Path(filename or "upload.bin").name or "upload.bin"
        suffix = Path(original).suffix.lower()
        if not suffix or not _SUFFIX_RE.match(suffix):
            suffix = ".bin"
        return original, suffix

    def save(self, reader: BinaryIO, filename: str | None) -> FileRecord:
        self.root.mkdir(parents=True, exist_ok=True)
        file_id = f"f_{uuid.uuid4().hex}"
        original, suffix = self._suffix(filename or "upload.bin")
        temp_path = self.root / f".{file_id}.part"
        binary_path = self.root / f"{file_id}{suffix}"
        digest = hashlib.sha256()
        size = 0

        try:
            with temp_path.open("wb") as handle:
                while True:
                    chunk = reader.read(self.chunk_size)
                    if not chunk:
                        break
                    size += len(chunk)
                    if self.max_bytes and size > self.max_bytes:
                        raise FileStoreError(
                            "upload_limit_exceeded",
                            f"上传超过运维配置的上限 {self.max_bytes} 字节",
                            413,
                        )
                    digest.update(chunk)
                    handle.write(chunk)
            if size == 0:
                raise FileStoreError("empty_file", "上传文件为空", 400)
            temp_path.replace(binary_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        created_at = datetime.now(UTC)
        expires_at = (
            created_at + timedelta(seconds=self.ttl_seconds) if self.ttl_seconds else None
        )
        meta = {
            "file_id": file_id,
            "filename": original,
            "suffix": suffix,
            "size": size,
            "sha256": digest.hexdigest(),
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
        }
        meta_path = self._meta_path(file_id)
        meta_tmp = meta_path.with_suffix(".json.tmp")
        meta_tmp.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        meta_tmp.replace(meta_path)
        return FileRecord(
            file_id=file_id,
            filename=original,
            suffix=suffix,
            size=size,
            sha256=str(meta["sha256"]),
            created_at=created_at,
            expires_at=expires_at,
            path=binary_path,
        )

    def record(self, file_id: str) -> FileRecord:
        if not FILE_ID_RE.match(file_id or ""):
            raise FileStoreError("invalid_file_id", "文件 ID 格式不合法", 400)
        meta_path = self._meta_path(file_id)
        if not meta_path.is_file():
            raise FileStoreError("file_not_found", "文件不存在或已过期", 404)
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FileStoreError("file_not_found", "文件元数据损坏", 404) from exc

        suffix = str(meta.get("suffix") or ".bin")
        binary_path = self.root / f"{file_id}{suffix}"
        expires_raw = meta.get("expires_at")
        expires_at = _parse_datetime(str(expires_raw)) if expires_raw else None
        if expires_at is not None and expires_at <= datetime.now(UTC):
            binary_path.unlink(missing_ok=True)
            meta_path.unlink(missing_ok=True)
            raise FileStoreError("file_expired", "文件已过期，请重新上传", 410)
        if not binary_path.is_file():
            raise FileStoreError("file_not_found", "文件内容不存在", 404)

        created_raw = meta.get("created_at")
        created_at = (
            _parse_datetime(str(created_raw))
            if created_raw
            else datetime.fromtimestamp(binary_path.stat().st_mtime, tz=UTC)
        )
        return FileRecord(
            file_id=file_id,
            filename=str(meta.get("filename") or binary_path.name),
            suffix=suffix,
            size=int(meta.get("size") or binary_path.stat().st_size),
            sha256=str(meta.get("sha256") or ""),
            created_at=created_at,
            expires_at=expires_at,
            path=binary_path,
        )

    def resolve(self, file_id: str) -> Path:
        return self.record(file_id).path

    def delete(self, file_id: str) -> bool:
        if not FILE_ID_RE.match(file_id or ""):
            raise FileStoreError("invalid_file_id", "文件 ID 格式不合法", 400)
        removed = False
        for path in self.root.glob(f"{file_id}.*"):
            path.unlink(missing_ok=True)
            removed = True
        return removed

    def cleanup_expired(self) -> int:
        removed = 0
        now = datetime.now(UTC)
        if not self.root.is_dir():
            return 0
        for meta_path in self.root.glob("f_*.json"):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                expires_raw = meta.get("expires_at")
                if not expires_raw:
                    continue
                if _parse_datetime(str(expires_raw)) > now:
                    continue
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            file_id = meta_path.stem
            for path in self.root.glob(f"{file_id}.*"):
                path.unlink(missing_ok=True)
            removed += 1
        return removed
