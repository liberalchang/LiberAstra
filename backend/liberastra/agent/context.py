"""把附件、节点引用和文本组装成模型消息；图片缩到长边 1568px，视频抽帧。"""

from __future__ import annotations

import base64
import io
import math
import mimetypes
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from liberastra.models import Asset
from liberastra.storage import resolve

MAX_IMAGE_EDGE = 1568
MAX_TEXT_CHARS = 20_000
MAX_VIDEO_FRAMES = 5

VISION_REQUIRED = (
    "当前模型不支持视觉输入。请换一个带视觉能力的模型、把附件设为「仅节点使用」，"
    "或去掉图片、视频后再发送。"
)


def _asset(db: Session, owner_id: int, asset_id: Any) -> Asset:
    try:
        aid = int(asset_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="附件 asset_id 无效"
        ) from exc
    asset = db.get(Asset, aid)
    if asset is None or asset.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"附件不存在: {aid}")
    return asset


def _image_part(asset: Asset) -> dict[str, Any]:
    path = resolve(asset.path)
    try:
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened)
            if max(image.size) > MAX_IMAGE_EDGE:
                image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"图片无法读取: {asset.path}"
        ) from exc
    data = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}}


def _video_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return 0.0
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return max(0.0, float(result.stdout.strip()))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 0.0


def _video_parts(asset: Asset) -> list[dict[str, Any]]:
    path = resolve(asset.path)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return [
            {
                "type": "text",
                "text": f"视频附件 #{asset.id}（{asset.path}）：本机缺少 ffmpeg，无法抽帧。",
            }
        ]
    duration = _video_duration(path)
    count = 5 if 3 <= duration <= 10 else 4 if duration < 3 else 6
    count = min(MAX_VIDEO_FRAMES + 1, max(1, count))
    timestamps = (
        [duration * (index + 0.5) / count for index in range(count)]
        if duration > 0
        else [index for index in range(count)]
    )
    parts: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="agent-video-") as folder:
        for index, timestamp in enumerate(timestamps):
            target = Path(folder) / f"frame_{index}.jpg"
            if duration > 0:
                command = [
                    ffmpeg,
                    "-y",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{timestamp:.3f}",
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    str(target),
                ]
            else:
                command = [
                    ffmpeg,
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    str(path),
                    "-vf",
                    f"select=eq(n\\,{math.floor(timestamp) * 24})",
                    "-frames:v",
                    "1",
                    str(target),
                ]
            try:
                subprocess.run(command, capture_output=True, timeout=30, check=False)
            except (OSError, subprocess.TimeoutExpired):
                continue
            if not target.is_file() or target.stat().st_size == 0:
                continue
            with Image.open(target) as image:
                if max(image.size) > MAX_IMAGE_EDGE:
                    image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGB")
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
            data = base64.b64encode(buffer.getvalue()).decode("ascii")
            parts.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}}
            )
        if parts:
            parts.append(
                {
                    "type": "text",
                    "text": (
                        f"以上是视频附件 #{asset.id}（{asset.path}）"
                        f"按时间均匀抽取的 {len(parts)} 帧。"
                    ),
                }
            )
    if not parts:
        parts.append(
            {"type": "text", "text": f"视频附件 #{asset.id}（{asset.path}）无法抽帧。"}
        )
    return parts


def _text_asset_part(asset: Asset) -> dict[str, Any]:
    path = resolve(asset.path)
    try:
        body = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        body = ""
    body = body[:MAX_TEXT_CHARS]
    return {"type": "text", "text": f"文本附件 #{asset.id}（{asset.path}）：\n{body}"}


def _media_parts(asset: Asset) -> list[dict[str, Any]]:
    if asset.kind == "image":
        return [_image_part(asset)]
    if asset.kind == "video":
        return _video_parts(asset)
    if asset.kind == "text":
        return [_text_asset_part(asset)]
    if asset.kind == "audio":
        return [
            {
                "type": "text",
                "text": (
                    f"音频附件 #{asset.id}（{asset.path}）没有直接送入模型；"
                    "可先调用 asr 工具转写。"
                ),
            }
        ]
    return [{"type": "text", "text": f"附件 #{asset.id} 类型为 {asset.kind}，未附带内容。"}]


def _attachment_label(attachment: dict[str, Any], asset: Asset) -> str:
    meta = asset.meta or {}
    name = str(
        attachment.get("name") or meta.get("source_name") or meta.get("name") or asset.path
    )
    return name.replace("\n", " ")[:120]


def _ref_text(ref: dict[str, Any], *, media_included: bool) -> str:
    title = str(ref.get("title") or ref.get("node_id") or "节点")
    var_name = str(ref.get("var_name") or "")
    handle = f"@{var_name}" if var_name else f"@{title}"
    lines = [f"【画布节点引用】{handle}（{title}）"]
    config = ref.get("config")
    if isinstance(config, dict) and config:
        summary = "；".join(f"{key}={value}" for key, value in list(config.items())[:12])
        lines.append(f"配置：{summary}")
    if ref.get("text"):
        lines.append(f"文本产出：{str(ref['text'])[:4000]}")
    asset_ids = ref.get("asset_ids") or ref.get("assets") or []
    if asset_ids:
        ids = [
            str(item.get("asset_id")) if isinstance(item, dict) else str(item)
            for item in asset_ids[:20]
        ]
        lines.append(f"产出资产：{', '.join(ids)}")
    if not media_included and asset_ids:
        lines.append(
            "（当前模型不支持视觉，图片/视频未附带；仍可按节点 id 和变量名读取配置、连线、断线或改属性。）"
        )
    return "\n".join(lines)


def assemble_user_content(
    db: Session,
    owner_id: int,
    payload: dict[str, Any],
    *,
    vision: bool,
) -> list[dict[str, Any]]:
    """组装一条用户消息的多模态 parts；需要视觉而模型没有时抛 400。

    附件按 send_to_model 分流：发给模型的图片/视频才要求视觉；仅节点附件只给
    asset_id/kind/name，供 Agent 写入画布节点。
    """
    text = str(payload.get("text") or "").strip()
    attachments = payload.get("attachments") or []
    refs = payload.get("refs") or []
    if not isinstance(attachments, list):
        attachments = []
    if not isinstance(refs, list):
        refs = []

    parts: list[dict[str, Any]] = []
    added_assets: set[int] = set()

    def add_media(asset: Asset) -> None:
        if asset.id in added_assets:
            return
        added_assets.add(asset.id)
        parts.extend(_media_parts(asset))

    if text:
        parts.append({"type": "text", "text": text[:MAX_TEXT_CHARS]})

    model_assets: list[Asset] = []
    attachment_lines: list[str] = []
    seen_attachments: set[int] = set()
    needs_vision = False
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        if attachment.get("asset_id") is None:
            continue
        asset = _asset(db, owner_id, attachment["asset_id"])
        if asset.id in seen_attachments:
            continue
        seen_attachments.add(asset.id)
        send_to_model = attachment.get("send_to_model") is not False
        if send_to_model:
            model_assets.append(asset)
            needs_vision = needs_vision or asset.kind in {"image", "video"}
            note = "已按模型附件处理，也可用于画布节点"
        else:
            note = "仅用于画布节点，未发送媒体内容"
        attachment_lines.append(
            f"- asset_id={asset.id}, kind={asset.kind}, "
            f"name={_attachment_label(attachment, asset)}（{note}）"
        )

    if needs_vision and not vision:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=VISION_REQUIRED)

    if attachment_lines:
        parts.append({"type": "text", "text": "附件：\n" + "\n".join(attachment_lines)})

    for asset in model_assets:
        add_media(asset)

    for ref in refs:
        if not isinstance(ref, dict):
            continue
        parts.append({"type": "text", "text": _ref_text(ref, media_included=vision)})
        if not vision:
            continue
        for item in ref.get("assets") or []:
            if isinstance(item, dict) and item.get("asset_id") is not None:
                add_media(_asset(db, owner_id, item["asset_id"]))
        for raw_id in ref.get("asset_ids") or []:
            if isinstance(raw_id, dict):
                raw_id = raw_id.get("asset_id")
            if raw_id is not None:
                add_media(_asset(db, owner_id, raw_id))
    if not parts:
        parts.append({"type": "text", "text": ""})
    return parts


def mime_for(path: str, fallback: str | None = None) -> str:
    """storage/local.py 的 mime 表不全时补全常见扩展名。"""
    guessed = mimetypes.guess_type(path)[0]
    return guessed or fallback or "application/octet-stream"
