"""背景音乐库路由：上传自动入库、列表、删除、内容试听。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from liberastra.api.deps import CurrentUser
from liberastra.core.config import get_settings

router = APIRouter(prefix="/bgm", tags=["bgm"])

_ALLOWED_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
_MAX_BYTES = 50 * 1024 * 1024

_MIME_BY_EXT = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
}


def _bgm_dir() -> Path:
    d = get_settings().data_dir / "bgm"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_name(filename: str) -> str:
    """去掉目录与危险字符，保留中文与常见符号。"""
    name = Path(filename).name
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "bgm"


def _resolve(name: str) -> Path:
    path = (_bgm_dir() / Path(name).name).resolve()
    if not path.is_relative_to(_bgm_dir().resolve()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法文件名")
    return path


@router.get("")
def list_bgm(user: CurrentUser) -> list[dict]:
    root = _bgm_dir()
    items = [
        {"name": p.name, "size": p.stat().st_size}
        for p in sorted(root.iterdir())
        if p.is_file() and p.suffix.lower() in _ALLOWED_EXT
    ]
    return items


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_bgm(user: CurrentUser, file: Annotated[UploadFile, File()]) -> dict:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空文件")
    if len(content) > _MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="音乐文件不能超过 50MB")
    name = _safe_name(file.filename or "bgm.mp3")
    if Path(name).suffix.lower() not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的格式，可用: {'/'.join(sorted(_ALLOWED_EXT))}",
        )
    dest = _resolve(name)
    if dest.exists():  # 同名自动加序号，不覆盖已有音乐
        stem, ext = dest.stem, dest.suffix
        i = 2
        while dest.exists():
            dest = _resolve(f"{stem}-{i}{ext}")
            i += 1
    dest.write_bytes(content)
    return {"name": dest.name, "size": dest.stat().st_size}


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bgm(name: str, user: CurrentUser) -> None:
    path = _resolve(name)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="音乐不存在")
    path.unlink()


@router.get("/{name}/content")
def bgm_content(name: str, user: CurrentUser) -> FileResponse:
    path = _resolve(name)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="音乐不存在")
    return FileResponse(path, media_type=_MIME_BY_EXT.get(path.suffix.lower(), "application/octet-stream"))
