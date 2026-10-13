"""ASR 能力服务：asr.transcribe 任务 runner，统一导出 txt/srt/vtt/json。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext, JobManager
from liberastra.media.subtitles import EXPORTERS
from liberastra.models import Job
from liberastra.services.providers import build_asr_adapter, pick_provider
from liberastra.storage import create_asset, resolve, save_bytes

_SUBTITLE_FORMATS = {"srt", "vtt"}


async def run_asr_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    provider = pick_provider(db, "asr", job.provider_id)
    adapter = build_asr_adapter(provider)
    params = job.params

    ctx.report(db, job, progress=0.1, step="transcribe")
    result = await adapter.transcribe(
        file_path=str(resolve(params["file_path"])),
        language=params.get("language"),
        task=params.get("task", "transcribe"),
        model=job.model,
    )
    if ctx.cancelled():
        return []

    outputs: list[dict[str, Any]] = [{"type": "text", "content": result.text}]
    formats = params.get("formats", ["txt", "srt", "vtt", "json"])
    for i, fmt in enumerate(formats):
        exporter = EXPORTERS.get(fmt)
        if exporter is None:
            continue
        rel_path = f"outputs/{job.id}/transcript.{fmt}"
        save_bytes(exporter(result).encode("utf-8"), rel_path)
        asset = create_asset(
            db,
            kind="subtitle" if fmt in _SUBTITLE_FORMATS else "text",
            rel_path=rel_path,
            job_id=job.id,
            owner_id=job.owner_id,
            meta={"format": fmt, "provider": provider.name},
        )
        outputs.append(
            {
                "type": "asset",
                "asset_id": asset.id,
                "format": fmt,
                "filename": f"transcript.{fmt}",
            }
        )
        ctx.report(db, job, progress=0.3 + 0.7 * (i + 1) / len(formats))
    return outputs


def register_asr_jobs(manager: JobManager) -> None:
    manager.register("asr.transcribe", run_asr_job)
