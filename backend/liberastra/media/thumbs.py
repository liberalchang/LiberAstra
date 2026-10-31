"""列表用的小图缓存。原图和原视频只在打开预览或下载时读取。

图片缩到长边 480 的 WebP。视频只抽一帧，避免把整条片子送进浏览器。
模板预览按 HTML 的修改时间落盘，文件没变就不再启动浏览器。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from liberastra.providers.base import ProviderError
from liberastra.services.templates import ASPECT_DIRS
from liberastra.storage import data_dir

THUMB_MAX_SIDE = 480
_WEBP_QUALITY = 80


def thumbs_root() -> Path:
    path = data_dir() / "thumbs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def asset_thumb_path(asset_id: int, source: Path | None = None) -> Path:
    """缩略图路径。带上源文件时，文件名含大小和修改时间，源文件一换就会重新生成。"""
    root = thumbs_root() / "assets"
    if source is None:
        return root / f"{asset_id}.webp"
    stat = source.stat()
    return root / f"{asset_id}_{stat.st_size}_{stat.st_mtime_ns}.webp"


def list_asset_thumbs(asset_id: int) -> list[Path]:
    root = thumbs_root() / "assets"
    if not root.exists():
        return []
    found = [root / f"{asset_id}.webp", *root.glob(f"{asset_id}_*.webp")]
    return [path for path in found if path.is_file()]


def remove_asset_thumb(asset_id: int, *, keep: Path | None = None) -> None:
    """删掉这个资产的缩略图。keep 是刚按当前文件写成的那一张。"""
    kept = keep.resolve() if keep is not None else None
    for path in list_asset_thumbs(asset_id):
        if kept is not None and path.resolve() == kept:
            continue
        path.unlink(missing_ok=True)


def _encode_webp(image: Image.Image, max_side: int) -> bytes:
    frame = ImageOps.exif_transpose(image)
    if frame.mode == "P":
        frame = frame.convert("RGBA")
    elif frame.mode not in ("RGB", "RGBA"):
        frame = frame.convert("RGB")
    frame.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buf = BytesIO()
    frame.save(buf, format="WEBP", quality=_WEBP_QUALITY, method=4)
    return buf.getvalue()


def webp_thumb_bytes(data: bytes, max_side: int = THUMB_MAX_SIDE) -> bytes:
    """把已经在内存里的图片压成缩略图。模板预览的 JPEG 走这里。"""
    try:
        with Image.open(BytesIO(data)) as image:
            return _encode_webp(image, max_side)
    except UnidentifiedImageError as exc:
        raise ProviderError("无法读取图片，生成不了缩略图") from exc


def image_thumb_bytes(src: Path, max_side: int = THUMB_MAX_SIDE) -> bytes:
    """从磁盘上的图片生成缩略图字节。不放大比 480 更小的图。"""
    try:
        with Image.open(src) as image:
            return _encode_webp(image, max_side)
    except (UnidentifiedImageError, OSError) as exc:
        raise ProviderError("无法读取图片，生成不了缩略图") from exc


def _grab_frame(video: Path, at: str, dest_png: Path) -> bool:
    if dest_png.exists():
        dest_png.unlink()
    proc = subprocess.run(
        [
            "ffmpeg", "-y", "-ss", at, "-i", str(video),
            "-frames:v", "1",
            "-vf", "scale='min(480,iw)':-2",
            str(dest_png),
        ],
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0 and dest_png.exists() and dest_png.stat().st_size > 0


def extract_video_thumb(video: Path, dest: Path, max_side: int = THUMB_MAX_SIDE) -> None:
    """抽一帧写成 WebP。先试 0.5 秒，极短的片子再退回开头。"""
    if not shutil.which("ffmpeg"):
        raise ProviderError("未找到 ffmpeg，请安装后重试")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        frame = Path(tmp) / "frame.png"
        if not _grab_frame(video, "0.5", frame) and not _grab_frame(video, "0", frame):
            raise ProviderError("未能抽出视频画面")
        _write_atomic(dest, image_thumb_bytes(frame, max_side))


def _write_atomic(dest: Path, data: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(dest)


def store_asset_thumb(asset_id: int, data: bytes, source: Path | None = None) -> Path:
    dest = asset_thumb_path(asset_id, source)
    _write_atomic(dest, data)
    remove_asset_thumb(asset_id, keep=dest)
    return dest


def template_thumb_path(aspect: str, name: str, mtime_ns: int) -> Path:
    folder = ASPECT_DIRS.get(aspect, aspect.replace(":", "x"))
    return thumbs_root() / "templates" / f"{folder}_{name}_{mtime_ns}.webp"


def clear_template_thumbs(aspect: str, name: str, *, keep: Path | None = None) -> None:
    """删掉这个模板的旧预览。keep 是刚写好的那一张，留下来。"""
    folder = ASPECT_DIRS.get(aspect, aspect.replace(":", "x"))
    root = thumbs_root() / "templates"
    if not root.exists():
        return
    prefix = f"{folder}_{name}_"
    kept = keep.resolve() if keep is not None else None
    for path in root.glob(f"{prefix}*.webp"):
        tail = path.name[len(prefix) : -len(".webp")]
        if not tail.isdigit():
            continue
        if kept is not None and path.resolve() == kept:
            continue
        path.unlink(missing_ok=True)
