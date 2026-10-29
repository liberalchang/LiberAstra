"""画布功能节点任务：canvas.node —— 按工作流包 capability 分发到图像/视频执行路径。

产物统一打标 hidden + meta{canvas_temp, canvas_id, canvas_node}：
资源库默认不显示，用户在画布节点上点「保存到资源库」后发布。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext, JobManager
from liberastra.models import Job
from liberastra.pipelines.quick import job_path
from liberastra.pipelines.simple import (
    _apply_soundtrack,
    _rel_of,
    max_aligned_seconds,
    motion_prompt,
    motion_windows,
    render_avatar_takes,
    render_motion_takes,
    slice_audio_takes,
)
from liberastra.providers.base import ProviderError
from liberastra.providers.video.comfyui import ComfyUIVideo
from liberastra.services.image import produce_images
from liberastra.services.preferences import get_pref
from liberastra.services.providers import pick_provider
from liberastra.services.workflows import WorkflowPack, get_pack
from liberastra.storage import create_asset, resolve, save_bytes

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


def _filled_keys(pack: WorkflowPack, inputs: dict[str, Any], kind: str) -> list[str]:
    return [key for key, spec in pack.inputs.items() if spec.get("type") == kind and inputs.get(key)]


async def _run_canvas_avatar(
    db: Session,
    job: Job,
    ctx: JobContext,
    pack: WorkflowPack,
    inputs: dict[str, Any],
    *,
    wait_timeout: float,
    started: float,
) -> list[dict[str, Any]]:
    """时长跟上游音频走。超单段上限按时间切开，尾帧接力，不重新配音。"""
    provider = pick_provider(db, "video", job.provider_id)
    if provider.type != "comfyui":
        raise ProviderError("画布功能节点需要 ComfyUI 类型的视频 Provider")
    audio_keys = _filled_keys(pack, inputs, "audio")
    image_keys = _filled_keys(pack, inputs, "image")
    if not audio_keys:
        raise ProviderError("数字人需要连接音频")
    if not image_keys:
        raise ProviderError("数字人需要连接人物图片")
    length_spec = pack.inputs.get("length") if "length" in pack.inputs else {}
    fps = float(pack.fps or 24)
    ceiling = max_aligned_seconds(fps, length_spec or {})
    audio_rel = str(inputs[audio_keys[0]])
    base_inputs = {key: value for key, value in inputs.items() if key not in ("length", "frames")}
    takes = await slice_audio_takes(
        resolve(audio_rel),
        ceiling=ceiling,
        rel_path=audio_rel,
        work=lambda name: job_path(job, name),
        rel_of=_rel_of,
    )
    adapter = ComfyUIVideo(provider.base_url)

    async def generate(
        segment_inputs: dict[str, Any], on_progress: Callable[[float], None]
    ) -> list[tuple[str, bytes]]:
        videos, _texts = await adapter.generate(
            pack=pack,
            inputs=segment_inputs,
            on_progress=on_progress,
            wait_timeout=wait_timeout,
        )
        return videos

    final = await render_avatar_takes(
        takes=takes,
        first_image=str(inputs[image_keys[0]]),
        base_inputs=base_inputs,
        length_spec=length_spec,
        fps=fps,
        image_key=image_keys[0],
        audio_key=audio_keys[0],
        custom_prompt=str(inputs.get("prompt") or ""),
        generate=generate,
        work=lambda name: job_path(job, name),
        rel_of=_rel_of,
        report=lambda progress, step: ctx.report(db, job, progress=progress, step=step),
        cancelled=ctx.cancelled,
    )
    if final is None or ctx.cancelled():
        return []
    final = await _apply_soundtrack(final, job.params)
    return _save_outputs(
        db, job, ctx, "video", [(final.name, final.read_bytes())], provider.name, time.monotonic() - started
    )


async def _run_canvas_motion(
    db: Session,
    job: Job,
    ctx: JobContext,
    pack: WorkflowPack,
    inputs: dict[str, Any],
    *,
    wait_timeout: float,
    started: float,
) -> list[dict[str, Any]]:
    """时长跟参考视频走。超单段上限分段，下一张人物图用上一段尾帧。"""
    from liberastra.media import ffmpeg

    provider = pick_provider(db, "video", job.provider_id)
    if provider.type != "comfyui":
        raise ProviderError("画布功能节点需要 ComfyUI 类型的视频 Provider")
    video_keys = _filled_keys(pack, inputs, "video")
    image_keys = _filled_keys(pack, inputs, "image")
    if not video_keys:
        raise ProviderError("动作迁移需要连接参考视频")
    if not image_keys:
        raise ProviderError("动作迁移需要连接人物图片")
    source = resolve(str(inputs[video_keys[0]]))
    image_paths = [str(inputs[key]) for key in image_keys]
    fps = float(pack.fps or 24)
    length_spec = pack.inputs.get("length") if "length" in pack.inputs else {}
    total = await ffmpeg.probe_duration(source)
    windows = motion_windows(total, fps, length_spec or {})
    prompt_text = motion_prompt(str(inputs.get("prompt") or ""), len(image_paths))
    base_inputs = {key: value for key, value in inputs.items() if key not in ("length", "frames", "prompt")}
    adapter = ComfyUIVideo(provider.base_url)

    async def generate(
        segment_inputs: dict[str, Any], on_progress: Callable[[float], None]
    ) -> list[tuple[str, bytes]]:
        videos, _texts = await adapter.generate(
            pack=pack,
            inputs=segment_inputs,
            on_progress=on_progress,
            wait_timeout=wait_timeout,
        )
        return videos

    final = await render_motion_takes(
        source=source,
        image_paths=image_paths,
        prompt_text=prompt_text,
        base_inputs=base_inputs,
        windows=windows,
        fps=fps,
        video_key=video_keys[0],
        image_keys=image_keys,
        generate=generate,
        work=lambda name: job_path(job, name),
        rel_of=_rel_of,
        report=lambda progress, step: ctx.report(db, job, progress=progress, step=step),
        cancelled=ctx.cancelled,
    )
    if final is None or ctx.cancelled():
        return []
    final = await _apply_soundtrack(final, job.params, reference=source)
    return _save_outputs(
        db, job, ctx, "video", [(final.name, final.read_bytes())], provider.name, time.monotonic() - started
    )


async def _run_canvas_analysis(
    db: Session,
    job: Job,
    ctx: JobContext,
    pack: WorkflowPack,
    inputs: dict[str, Any],
    *,
    wait_timeout: float,
    started: float,
) -> list[dict[str, Any]]:
    """跑分析包，文字写入文本资产，供下游 {{变量名}} 引用。"""
    from liberastra.providers.analysis.comfyui import ComfyUIAnalysis

    provider = pick_provider(db, "image", job.provider_id)
    if provider.type != "comfyui":
        raise ProviderError("画布功能节点需要 ComfyUI 类型的图像 Provider")
    ctx.report(db, job, progress=0.1, step="analyze")
    text = await ComfyUIAnalysis(provider.base_url).analyze(
        pack=pack,
        inputs=inputs,
        wait_timeout=wait_timeout,
    )
    if ctx.cancelled():
        return []
    cleaned = text.strip()
    if not cleaned:
        raise ProviderError("分析工作流完成但未产出文本")
    rel_path = f"outputs/{job.id}/analysis.txt"
    save_bytes(cleaned.encode("utf-8"), rel_path)
    asset = create_asset(
        db,
        kind="text",
        rel_path=rel_path,
        job_id=job.id,
        owner_id=job.owner_id,
        hidden=True,
        meta=_canvas_meta(
            job,
            {"provider": provider.name, "duration_s": round(time.monotonic() - started, 1)},
        ),
    )
    ctx.report(db, job, progress=1.0)
    return [
        {"type": "asset", "asset_id": asset.id, "kind": "text", "filename": "analysis.txt"},
        {"type": "text", "content": cleaned},
    ]


async def _run_model_node(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """云端模型节点：按 sub_capability 调用图像或视频适配器。"""
    from liberastra.services.model_media import generate_model_media, output_kind

    params = job.params
    sub = str(params.get("sub_capability") or "")
    kind = output_kind(sub)
    capability = "video" if kind == "video" else "image"
    provider = pick_provider(db, capability, job.provider_id)
    ctx.report(db, job, progress=0.05, step="generate")
    started = time.monotonic()
    files = await generate_model_media(
        provider,
        model=str(params.get("model") or job.model or ""),
        sub_capability=sub,
        prompt=str(params.get("prompt") or ""),
        inputs=dict(params.get("inputs") or {}),
        on_progress=lambda progress: ctx.report(db, job, progress=0.05 + 0.85 * progress),
        wait_timeout=float(get_pref(db, "comfy_wait_timeout_seconds")),
    )
    if ctx.cancelled():
        return []
    return _save_outputs(db, job, ctx, kind, files, provider.name, time.monotonic() - started)


async def run_canvas_node_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    params = job.params
    if params.get("target_type") == "model":
        return await _run_model_node(db, job, ctx)
    pack = get_pack(str(params["workflow"]))
    inputs = dict(params.get("inputs") or {})
    wait_timeout = float(get_pref(db, "comfy_wait_timeout_seconds"))
    started = time.monotonic()

    if pack.capability == "analysis":
        return await _run_canvas_analysis(
            db, job, ctx, pack, inputs, wait_timeout=wait_timeout, started=started
        )
    if pack.capability == "avatar":
        return await _run_canvas_avatar(
            db, job, ctx, pack, inputs, wait_timeout=wait_timeout, started=started
        )
    if pack.capability == "motion":
        return await _run_canvas_motion(
            db, job, ctx, pack, inputs, wait_timeout=wait_timeout, started=started
        )

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
