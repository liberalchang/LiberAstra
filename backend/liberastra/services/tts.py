"""TTS 能力服务：tts.synthesize 任务 runner。"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext, JobManager
from liberastra.models import Job
from liberastra.services.preferences import get_pref
from liberastra.services.providers import build_tts_adapter, pick_provider
from liberastra.services.workflows import get_pack
from liberastra.storage import create_asset, save_bytes

_EXT_BY_FORMAT = {"ogg_opus": "ogg", "opus": "ogg"}


async def run_tts_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    provider = pick_provider(db, "tts", job.provider_id)
    adapter = build_tts_adapter(provider, db=db)
    params = job.params
    fmt = params.get("format", "mp3")

    ctx.report(db, job, progress=0.1, step="synthesize")
    started = time.monotonic()
    filename: str | None = None
    if provider.type == "comfyui":
        # 语音工作流：text/voice/ref_audio 按 manifest 声明注入
        pack = get_pack(params["workflow"])
        inputs = dict(params.get("inputs", {}))
        if "text" in pack.inputs:
            inputs["text"] = params["text"]
        if "voice" in pack.inputs and params.get("voice"):
            inputs["voice"] = params["voice"]
        ref_audio = params.get("options", {}).get("ref_audio")
        if ref_audio and "ref_audio" in pack.inputs:
            inputs["ref_audio"] = ref_audio
        filename, audio = await adapter.synthesize_pack(
            pack=pack,
            inputs=inputs,
            on_progress=lambda p: ctx.report(db, job, progress=0.1 + 0.85 * p),
            wait_timeout=float(get_pref(db, "comfy_wait_timeout_seconds")),
        )
    else:
        audio = await adapter.synthesize(
            text=params["text"],
            voice=params["voice"],
            model=job.model,
            fmt=fmt,
            **params.get("options", {}),
        )
    if ctx.cancelled():
        return []

    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1]
    else:
        ext = _EXT_BY_FORMAT.get(fmt, fmt)
    rel_path = f"outputs/{job.id}/speech.{ext}"
    save_bytes(audio, rel_path)
    meta = {
        "voice": params.get("voice"),
        "format": ext,
        "provider": provider.name,
        "workflow": params.get("workflow"),
        "text": params["text"][:500],
        "model": job.model,
        "duration_s": round(time.monotonic() - started, 1),
    }
    asset = create_asset(
        db,
        kind="audio",
        rel_path=rel_path,
        job_id=job.id,
        owner_id=job.owner_id,
        meta={k: v for k, v in meta.items() if v not in (None, "")},
    )
    ctx.report(db, job, progress=1.0)
    return [
        {"type": "asset", "asset_id": asset.id, "kind": "audio", "filename": f"speech.{ext}"}
    ]


def register_tts_jobs(manager: JobManager) -> None:
    manager.register("tts.synthesize", run_tts_job)
