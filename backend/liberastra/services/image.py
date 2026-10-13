"""图像能力服务：image.generate / image.edit 任务 runner、提示词优化。"""

from __future__ import annotations

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


async def run_image_generate_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    provider = pick_provider(db, "image", job.provider_id)
    adapter = build_image_adapter(provider)
    params = job.params

    ctx.report(db, job, progress=0.05, step="generate")
    if provider.type == "comfyui":
        pack = get_pack(params["workflow"])
        images = await adapter.generate(
            pack=pack,
            inputs=params.get("inputs", {}),
            on_progress=lambda p: ctx.report(db, job, progress=0.05 + 0.85 * p),
        )
    else:
        images = await adapter.generate(
            prompt=params["prompt"],
            size=params.get("size", "1024x1024"),
            n=params.get("n", 1),
            model=job.model,
            **params.get("options", {}),
        )
    if ctx.cancelled():
        return []
    return _save_images(db, job, ctx, provider.name, images)


async def run_image_edit_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    provider = pick_provider(db, "image", job.provider_id)
    adapter = build_image_adapter(provider)
    params = job.params

    ctx.report(db, job, progress=0.05, step="edit")
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
    return _save_images(db, job, ctx, provider.name, images)


def _save_images(
    db: Session,
    job: Job,
    ctx: JobContext,
    provider_name: str,
    images: list[tuple[str, bytes]],
) -> list[dict[str, Any]]:
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
            meta={"provider": provider_name, "source_name": filename},
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
