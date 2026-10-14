"""图像能力服务：image.generate / image.edit 任务 runner、提示词优化。"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext, JobManager
from liberastra.models import Job
from liberastra.providers.base import ProviderError
from liberastra.services.providers import build_image_adapter, build_llm_adapter, pick_provider
from liberastra.services.workflows import get_pack
from liberastra.storage import create_asset, resolve, save_bytes

OPTIMIZE_SYSTEM_PROMPT = (
    "你是图像生成提示词专家。把用户的简短描述扩写成一段高质量文生图提示词，"
    "包含主体、细节、构图、光线、风格与画质词。直接输出提示词本身，不要解释。"
    "用户输入是中文就输出中文，是英文就输出英文。"
)


async def produce_images(
    provider,  # noqa: ANN001 Provider
    *,
    workflow: str | None = None,
    inputs: dict[str, Any] | None = None,
    prompt: str = "",
    size: str = "1024x1024",
    n: int = 1,
    model: str | None = None,
    options: dict[str, Any] | None = None,
    on_progress: Any = None,
) -> list[tuple[str, bytes]]:
    """按 Provider 类型生成图像（流水线与 image.generate 共用）。"""
    adapter = build_image_adapter(provider)
    if provider.type == "comfyui":
        pack = get_pack(workflow or "")
        return await adapter.generate(pack=pack, inputs=inputs or {}, on_progress=on_progress)
    return await adapter.generate(
        prompt=prompt, size=size, n=n, model=model, **(options or {})
    )


async def run_image_generate_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    provider = pick_provider(db, "image", job.provider_id)
    params = job.params

    ctx.report(db, job, progress=0.05, step="generate")
    started = time.monotonic()
    images = await produce_images(
        provider,
        workflow=params.get("workflow"),
        inputs=params.get("inputs"),
        prompt=params.get("prompt", ""),
        size=params.get("size", "1024x1024"),
        n=params.get("n", 1),
        model=job.model,
        options=params.get("options"),
        on_progress=lambda p: ctx.report(db, job, progress=0.05 + 0.85 * p),
    )
    if ctx.cancelled():
        return []
    return _save_images(db, job, ctx, provider.name, images, duration_s=time.monotonic() - started)


async def run_image_edit_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    provider = pick_provider(db, "image", job.provider_id)
    adapter = build_image_adapter(provider)
    params = job.params

    ctx.report(db, job, progress=0.05, step="edit")
    started = time.monotonic()
    if provider.type == "comfyui":
        pack = get_pack(params["workflow"])
        inputs = dict(params.get("inputs", {}))
        # 第一张上传图映射到第一个 image 类型输入
        image_keys = [k for k, s in pack.inputs.items() if s.get("type") == "image"]
        for key, path in zip(image_keys, params.get("image_paths", []), strict=False):
            inputs[key] = path
        images = await adapter.generate(
            pack=pack,
            inputs=inputs,
            on_progress=lambda p: ctx.report(db, job, progress=0.05 + 0.85 * p),
        )
    else:
        first = params["image_paths"][0]
        local = resolve(first)
        images = await adapter.edit(
            image=(local.name, local.read_bytes()),
            prompt=params["prompt"],
            size=params.get("size", "1024x1024"),
            model=job.model,
            **params.get("options", {}),
        )
    if ctx.cancelled():
        return []
    return _save_images(db, job, ctx, provider.name, images, duration_s=time.monotonic() - started)


def _save_images(
    db: Session,
    job: Job,
    ctx: JobContext,
    provider_name: str,
    images: list[tuple[str, bytes]],
    *,
    duration_s: float | None = None,
) -> list[dict[str, Any]]:
    params = job.params
    inputs = params.get("inputs") or {}
    options = params.get("options") or {}
    width, height = inputs.get("width"), inputs.get("height")
    base_meta = {
        "provider": provider_name,
        "prompt": params.get("prompt") or inputs.get("prompt"),
        "negative_prompt": inputs.get("negative_prompt"),
        "workflow": params.get("workflow"),
        "size": params.get("size") or (f"{width}x{height}" if width and height else None),
        "model": job.model,
        "seed": inputs.get("seed", options.get("seed")),
        "duration_s": round(duration_s, 1) if duration_s is not None else None,
    }
    base_meta = {k: v for k, v in base_meta.items() if v not in (None, "")}

    outputs: list[dict[str, Any]] = []
    for i, (filename, content) in enumerate(images):
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "png"
        rel_path = f"outputs/{job.id}/image_{i}.{ext}"
        save_bytes(content, rel_path)
        asset = create_asset(
            db,
            kind="image",
            rel_path=rel_path,
            job_id=job.id,
            owner_id=job.owner_id,
            meta={**base_meta, "source_name": filename},
        )
        outputs.append(
            {"type": "asset", "asset_id": asset.id, "kind": "image", "filename": f"image_{i}.{ext}"}
        )
    ctx.report(db, job, progress=1.0)
    return outputs


async def optimize_prompt(db: Session, provider_id: int | None, prompt: str) -> str:
    """用 LLM 扩写提示词（同步快速调用）。"""
    provider = pick_provider(db, "llm", provider_id)
    adapter = build_llm_adapter(provider)
    try:
        return await adapter.chat(
            model=provider.extra.get("model", "") or "default",
            messages=[
                {"role": "system", "content": OPTIMIZE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
    except ProviderError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(f"提示词优化失败: {exc}") from exc


def register_image_jobs(manager: JobManager) -> None:
    manager.register("image.generate", run_image_generate_job)
    manager.register("image.edit", run_image_edit_job)
