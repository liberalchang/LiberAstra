"""媒体合成任务：media.concat —— 多段音频/视频按顺序拼接成整段（画布合成节点）。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext
from liberastra.media import ffmpeg
from liberastra.models import Asset, Job
from liberastra.providers.base import ProviderError
from liberastra.storage import create_asset, resolve


async def run_concat_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    params = job.params
    kind = str(params.get("kind") or "video")
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
    await ffmpeg.concat_media(paths, out, kind=kind, work_dir=resolve(f"outputs/{job.id}/concat_work"))
    if ctx.cancelled():
        return []
    asset = create_asset(
        db,
        kind=kind,
        rel_path=rel_path,
        job_id=job.id,
        owner_id=job.owner_id,
        hidden=True,
        meta={
            "canvas_temp": True,
            "canvas_id": params.get("canvas_id"),
            "canvas_node": params.get("node_id"),
            "sources": asset_ids,
            "segments": len(paths),
            "duration_s": round(time.monotonic() - started, 1),
        },
    )
    ctx.report(db, job, progress=1.0)
    return [{"type": "asset", "asset_id": asset.id, "kind": kind, "filename": out.name}]
