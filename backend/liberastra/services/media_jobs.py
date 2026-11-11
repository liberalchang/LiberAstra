"""媒体合成任务：media.concat —— 多段音频/视频拼接，或多张图片拼图（画布合成节点）。"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor
from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext
from liberastra.media import ffmpeg
from liberastra.models import Asset, Job
from liberastra.providers.base import ProviderError
from liberastra.storage import create_asset, resolve, save_bytes


def _gap_color(raw: Any) -> tuple[int, int, int]:
    text = str(raw or "#FFFFFF").strip()
    try:
        return ImageColor.getrgb(text)[:3]  # type: ignore[return-value]
    except ValueError:
        return (255, 255, 255)


def _concat_images(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """PIL 拼图：横排统一高度、竖排统一宽度、网格等比缩放居中。"""
    params = job.params
    asset_ids = [int(a) for a in (params.get("asset_ids") or [])]
    if len(asset_ids) < 2:
        raise ProviderError("图片合成至少需要两张输入")
    images: list[Image.Image] = []
    for asset_id in asset_ids:
        asset = db.get(Asset, asset_id)
        if asset is None or asset.owner_id != job.owner_id:
            raise ProviderError(f"素材不存在: {asset_id}")
        if asset.kind != "image":
            raise ProviderError(f"素材 {asset_id} 不是图片")
        with Image.open(resolve(asset.path)) as opened:
            images.append(opened.convert("RGB"))

    layout = str(params.get("layout") or "horizontal")
    gap = max(0, int(params.get("gap") if params.get("gap") is not None else 4))
    color = _gap_color(params.get("gap_color"))
    columns = max(1, int(params.get("columns") or 2))
    ctx.report(db, job, progress=0.3, step="concat")

    if layout == "vertical":
        width = max(image.width for image in images)
        scaled = [
            image
            if image.width == width
            else image.resize(
                (width, max(1, round(image.height * width / image.width))),
                Image.Resampling.LANCZOS,
            )
            for image in images
        ]
        height = sum(image.height for image in scaled) + gap * (len(scaled) - 1)
        canvas = Image.new("RGB", (max(1, width), max(1, height)), color)
        y = 0
        for image in scaled:
            canvas.paste(image, (0, y))
            y += image.height + gap
    elif layout == "grid":
        # 统一缩放到最矮图片的高度，再按行排版；避免不同宽高比在单元格里留下大片空白。
        columns = min(columns, len(images))
        rows = math.ceil(len(images) / columns)
        target_h = min(image.height for image in images)
        scaled = [
            image.resize(
                (max(1, round(image.width * target_h / image.height)), target_h),
                Image.Resampling.LANCZOS,
            )
            for image in images
        ]
        row_slices = [scaled[index : index + columns] for index in range(0, len(scaled), columns)]
        row_widths = [
            sum(image.width for image in row) + gap * max(0, len(row) - 1)
            for row in row_slices
        ]
        width = max(row_widths)
        height = rows * target_h + gap * (rows - 1)
        canvas = Image.new("RGB", (max(1, width), max(1, height)), color)
        y = 0
        for row, row_width in zip(row_slices, row_widths, strict=False):
            x = (width - row_width) // 2
            for image in row:
                canvas.paste(image, (x, y))
                x += image.width + gap
            y += target_h + gap
    else:
        layout = "horizontal"
        height = max(image.height for image in images)
        scaled = [
            image
            if image.height == height
            else image.resize(
                (max(1, round(image.width * height / image.height)), height),
                Image.Resampling.LANCZOS,
            )
            for image in images
        ]
        width = sum(image.width for image in scaled) + gap * (len(scaled) - 1)
        canvas = Image.new("RGB", (max(1, width), max(1, height)), color)
        x = 0
        for image in scaled:
            canvas.paste(image, (x, 0))
            x += image.width + gap

    import io

    rel_path = f"outputs/{job.id}/concat_0.png"
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    save_bytes(buffer.getvalue(), rel_path)
    visible = bool(params.get("visible", False))
    meta = {
        "canvas_temp": not visible,
        "canvas_id": params.get("canvas_id"),
        "canvas_node": params.get("node_id"),
        "sources": asset_ids,
        "layout": layout,
        "columns": columns,
        "gap": gap,
    }
    if params.get("tool_id"):
        meta["tool_id"] = str(params["tool_id"])
    asset = create_asset(
        db,
        kind="image",
        rel_path=rel_path,
        job_id=job.id,
        owner_id=job.owner_id,
        hidden=not visible,
        origin="output" if visible else "canvas",
        meta=meta,
    )
    ctx.report(db, job, progress=1.0)
    return [{"type": "asset", "asset_id": asset.id, "kind": "image", "filename": "concat_0.png"}]


async def run_extract_audio_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """从视频/音频提取完整音轨，或截取固定长度尾音。"""
    params = job.params
    asset_id = int(params.get("asset_id") or 0)
    asset = db.get(Asset, asset_id)
    if asset is None or asset.owner_id != job.owner_id:
        raise ProviderError("输入素材不存在")
    if asset.kind not in ("video", "audio"):
        raise ProviderError("音频提取只支持视频或音频输入")
    mode = "whole" if str(params.get("mode") or "") == "whole" else "tail"
    seconds = max(0.5, min(15.0, float(params.get("seconds") or 5)))
    ctx.report(db, job, progress=0.2, step="extract_audio")
    started = time.monotonic()
    rel_path = f"outputs/{job.id}/extract_audio.wav"
    out = resolve(rel_path)
    if mode == "tail":
        await ffmpeg.extract_audio_tail(resolve(asset.path), seconds, out)
    else:
        await ffmpeg.extract_audio(resolve(asset.path), out)
    if ctx.cancelled():
        return []
    visible = bool(params.get("visible", False))
    meta = {
        "canvas_temp": not visible,
        "canvas_id": params.get("canvas_id"),
        "canvas_node": params.get("node_id"),
        "tool_id": "audio_extract",
        "source_asset_id": asset.id,
        "mode": mode,
        "seconds": seconds if mode == "tail" else None,
        "duration_s": round(time.monotonic() - started, 1),
    }
    created = create_asset(
        db,
        kind="audio",
        rel_path=rel_path,
        job_id=job.id,
        owner_id=job.owner_id,
        hidden=not visible,
        origin="output" if visible else "canvas",
        meta=meta,
    )
    ctx.report(db, job, progress=1.0)
    return [{"type": "asset", "asset_id": created.id, "kind": "audio", "filename": out.name}]


async def run_concat_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    params = job.params
    kind = str(params.get("kind") or "video")
    if kind == "image":
        return _concat_images(db, job, ctx)
    if kind not in ("audio", "video"):
        raise ProviderError(f"不支持的合成类型: {kind}")
    asset_ids = [int(a) for a in (params.get("asset_ids") or [])]
    if not asset_ids:
        raise ProviderError("合成至少需要一段输入")

    paths: list[Path] = []
    for asset_id in asset_ids:
        asset = db.get(Asset, asset_id)
        if asset is None or asset.owner_id != job.owner_id:
            raise ProviderError(f"素材不存在: {asset_id}")
        if asset.kind != kind:
            raise ProviderError(f"素材 {asset_id} 类型是 {asset.kind}，与合成类型 {kind} 不符")
        paths.append(resolve(asset.path))

    ctx.report(db, job, progress=0.1, step="concat")
    started = time.monotonic()
    suffix = ".mp4" if kind == "video" else ".mp3"
    rel_path = f"outputs/{job.id}/concat_0{suffix}"
    out = resolve(rel_path)
    audio_fade_ms = max(0, min(200, int(params.get("audio_fade_ms") or 0)))
    await ffmpeg.concat_media(
        paths,
        out,
        kind=kind,
        work_dir=resolve(f"outputs/{job.id}/concat_work"),
        audio_fade_ms=audio_fade_ms,
    )
    audio_bed_asset_id = params.get("audio_bed_asset_id")
    if kind == "video" and audio_bed_asset_id not in (None, ""):
        bed = db.get(Asset, int(audio_bed_asset_id))
        if bed is None or bed.owner_id != job.owner_id or bed.kind != "audio":
            raise ProviderError("全片氛围底音频不存在或不是音频资产")
        bed_out = out.with_name("concat_bed.mp4")
        if str(params.get("audio_bed_mode") or "mix") == "replace":
            await ffmpeg.replace_audio_loop(out, resolve(bed.path), bed_out)
        else:
            await ffmpeg.add_bgm(
                video=out,
                bgm=resolve(bed.path),
                out=bed_out,
                bgm_volume=float(params.get("audio_bed_volume") or 0.2),
                loop=True,
            )
        out = bed_out
        rel_path = f"outputs/{job.id}/{out.name}"
    if ctx.cancelled():
        return []
    visible = bool(params.get("visible", False))
    meta = {
        "canvas_temp": not visible,
        "canvas_id": params.get("canvas_id"),
        "canvas_node": params.get("node_id"),
        "sources": asset_ids,
        "segments": len(paths),
        "duration_s": round(time.monotonic() - started, 1),
    }
    if audio_bed_asset_id not in (None, ""):
        meta["audio_bed_asset_id"] = int(audio_bed_asset_id)
        meta["audio_bed_mode"] = str(params.get("audio_bed_mode") or "mix")
    if params.get("tool_id"):
        meta["tool_id"] = str(params["tool_id"])
    asset = create_asset(
        db,
        kind=kind,
        rel_path=rel_path,
        job_id=job.id,
        owner_id=job.owner_id,
        hidden=not visible,
        origin="output" if visible else "canvas",
        meta=meta,
    )
    ctx.report(db, job, progress=1.0)
    return [{"type": "asset", "asset_id": asset.id, "kind": kind, "filename": out.name}]
