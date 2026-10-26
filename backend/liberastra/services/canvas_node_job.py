"""画布功能节点任务：canvas.node —— 按工作流包 capability 分发到图像/视频执行路径。

产物统一打标 hidden + meta{canvas_temp, canvas_id, canvas_node}：
资源库默认不显示，用户在画布节点上点「保存到资源库」后发布。
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext, JobManager
from liberastra.models import Job
from liberastra.providers.base import ProviderError
from liberastra.providers.video.comfyui import ComfyUIVideo
from liberastra.services.image import produce_images
from liberastra.services.preferences import get_pref
from liberastra.services.providers import pick_provider
from liberastra.services.workflows import get_pack
from liberastra.storage import create_asset, save_bytes

IMAGE_CAPS = ("t2i", "i2i", "upscale")
VIDEO_CAPS = ("t2v", "i2v", "avatar", "motion")


def _canvas_meta(job: Job, extra: dict[str, Any]) -> dict[str, Any]:
    params = job.params
    meta = {
        "workflow": params.get("workflow"),
        "prompt": (params.get("inputs") or {}).get("prompt"),
        "canvas_temp": True,
        "canvas_id": params.get("canvas_id"),
        "canvas_node": params.get("node_id"),
        **extra,
    }
    return {k: v for k, v in meta.items() if v not in (None, "")}


def _save_outputs(
    db: Session,
    job: Job,
    ctx: JobContext,
    kind: str,
    files: list[tuple[str, bytes]],
    provider_name: str,
    duration_s: float,
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for i, (filename, content) in enumerate(files):
        ext = filename.rsplit(".", 1)[-1] if "." in filename else ("png" if kind == "image" else "mp4")
        rel_path = f"outputs/{job.id}/{kind}_{i}.{ext}"
        save_bytes(content, rel_path)
        asset = create_asset(
            db,
            kind=kind,
            rel_path=rel_path,
            job_id=job.id,
            owner_id=job.owner_id,
            hidden=True,
            meta=_canvas_meta(
                job,
                {
                    "provider": provider_name,
                    "source_name": filename,
                    "duration_s": round(duration_s, 1),
                },
            ),
        )
        outputs.append(
            {"type": "asset", "asset_id": asset.id, "kind": kind, "filename": f"{kind}_{i}.{ext}"}
        )
    ctx.report(db, job, progress=1.0)
    return outputs


async def run_canvas_node_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    params = job.params
    pack = get_pack(str(params["workflow"]))
    inputs = dict(params.get("inputs") or {})
    wait_timeout = float(get_pref(db, "comfy_wait_timeout_seconds"))
    started = time.monotonic()

    if pack.capability in IMAGE_CAPS:
        provider = pick_provider(db, "image", job.provider_id)
        if provider.type != "comfyui":
            raise ProviderError("画布功能节点需要 ComfyUI 类型的图像 Provider")
        ctx.report(db, job, progress=0.05, step="generate")
        images = await produce_images(
            provider,
            workflow=pack.name,
            inputs=inputs,
            on_progress=lambda p: ctx.report(db, job, progress=0.05 + 0.85 * p),
            wait_timeout=wait_timeout,
        )
        if ctx.cancelled():
            return []
        return _save_outputs(db, job, ctx, "image", images, provider.name, time.monotonic() - started)

    if pack.capability in VIDEO_CAPS:
        provider = pick_provider(db, "video", job.provider_id)
        if provider.type != "comfyui":
            raise ProviderError("画布功能节点需要 ComfyUI 类型的视频 Provider")
        adapter = ComfyUIVideo(provider.base_url)
        ctx.report(db, job, progress=0.1, step="comfyui")
        videos, texts = await adapter.generate(
            pack=pack,
            inputs=inputs,
            on_progress=lambda p: ctx.report(db, job, progress=0.1 + 0.85 * p),
            wait_timeout=wait_timeout,
        )
        if ctx.cancelled():
            return []
        outputs = _save_outputs(
            db, job, ctx, "video", videos, provider.name, time.monotonic() - started
        )
        # 增强包等声明 outputs.texts 时,把增强提示词/报告一并带回
        for block in texts:
            if block.strip():
                outputs.append({"type": "text", "content": block})
        return outputs

    raise ProviderError(f"画布暂不支持该工作流包能力: {pack.capability}")


def register_canvas_jobs(manager: JobManager) -> None:
    manager.register("canvas.node", run_canvas_node_job)
    from liberastra.services.media_jobs import run_concat_job

    manager.register("media.concat", run_concat_job)
