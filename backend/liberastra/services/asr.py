"""ASR 能力服务：asr.transcribe 任务 runner，统一导出 txt/srt/vtt/json。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext, JobManager
from liberastra.media.subtitles import EXPORTERS
from liberastra.models import Job
from liberastra.services.providers import build_asr_adapter, pick_provider
from liberastra.storage import create_asset, resolve, save_bytes

_SUBTITLE_FORMATS = {"srt", "vtt"}

# 自动模式下的输出格式优先级：纯文本 → 结构化 → 字幕
_FORMAT_PRIORITY = ["txt", "json", "srt", "vtt"]


def _pick_format(formats: list[str] | None) -> str:
    """按请求顺序选第一个可导出的格式；都不可用时按内置优先级兜底。"""
    requested = [f for f in (formats or _FORMAT_PRIORITY) if f in EXPORTERS]
    if not requested:
        requested = [f for f in _FORMAT_PRIORITY if f in EXPORTERS]
    return requested[0]


async def run_asr_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    provider = pick_provider(db, "asr", job.provider_id)
    adapter = build_asr_adapter(provider)
    params = job.params

    ctx.report(db, job, progress=0.1, step="transcribe")
    started = time.monotonic()
    result = await adapter.transcribe(
        file_path=str(resolve(params["file_path"])),
        language=params.get("language"),
        task=params.get("task", "transcribe"),
        model=job.model,
    )
    if ctx.cancelled():
        return []

    outputs: list[dict[str, Any]] = [{"type": "text", "content": result.text}]
    base_meta = {
        "provider": provider.name,
        "source_name": Path(params["file_path"]).name,
        "language": params.get("language"),
        "model": job.model,
        "duration_s": round(time.monotonic() - started, 1),
    }
    base_meta = {k: v for k, v in base_meta.items() if v not in (None, "")}

    fmt = _pick_format(params.get("formats"))
    rel_path = f"outputs/{job.id}/transcript.{fmt}"
    save_bytes(EXPORTERS[fmt](result).encode("utf-8"), rel_path)
    kind = "subtitle" if fmt in _SUBTITLE_FORMATS else "text"
    asset = create_asset(
        db,
        kind=kind,
        rel_path=rel_path,
        job_id=job.id,
        owner_id=job.owner_id,
        meta={**base_meta, "format": fmt},
    )
    outputs.append(
        {"type": "asset", "asset_id": asset.id, "kind": kind, "format": fmt,
         "filename": f"transcript.{fmt}"}
    )
    ctx.report(db, job, progress=1.0)
    return outputs


def register_asr_jobs(manager: JobManager) -> None:
    manager.register("asr.transcribe", run_asr_job)
