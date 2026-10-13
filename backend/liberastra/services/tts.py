"""TTS 能力服务：tts.synthesize 任务 runner。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext, JobManager
from liberastra.models import Job
from liberastra.services.providers import build_tts_adapter, pick_provider
from liberastra.storage import create_asset, save_bytes

_EXT_BY_FORMAT = {"ogg_opus": "ogg", "opus": "ogg"}


async def run_tts_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    provider = pick_provider(db, "tts", job.provider_id)
    adapter = build_tts_adapter(provider)
    params = job.params
    fmt = params.get("format", "mp3")

    ctx.report(db, job, progress=0.1, step="synthesize")
    audio = await adapter.synthesize(
        text=params["text"],
        voice=params["voice"],
        model=job.model,
        fmt=fmt,
        **params.get("options", {}),
    )
    if ctx.cancelled():
        return []

    ext = _EXT_BY_FORMAT.get(fmt, fmt)
    rel_path = f"outputs/{job.id}/speech.{ext}"
    save_bytes(audio, rel_path)
    asset = create_asset(
        db,
        kind="audio",
        rel_path=rel_path,
        job_id=job.id,
        owner_id=job.owner_id,
        meta={"voice": params["voice"], "format": fmt, "provider": provider.name},
    )
    ctx.report(db, job, progress=1.0)
    return [
        {"type": "asset", "asset_id": asset.id, "kind": "audio", "filename": f"speech.{ext}"}
    ]


def register_tts_jobs(manager: JobManager) -> None:
    manager.register("tts.synthesize", run_tts_job)
