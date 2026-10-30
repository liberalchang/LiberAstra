"""图像路由：文生图、图生图/修复放大（统一为 edit）、提示词优化、深度图。"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.api.utils import wait_for_job
from liberastra.models import Asset, Job, Provider
from liberastra.providers.base import ProviderError
from liberastra.schemas.asset import AssetOut
from liberastra.schemas.image import (
    ImageGenerateRequest,
    PromptOptimizeRequest,
    PromptOptimizeResponse,
)
from liberastra.schemas.job import JobOut
from liberastra.services.image import optimize_prompt
from liberastra.services.plugins import depth_output_name
from liberastra.services.providers import build_adapter, pick_provider
from liberastra.storage import save_upload
from liberastra.storage.local import create_asset, resolve, save_bytes

router = APIRouter(prefix="/images", tags=["images"])


def _validate_workflow_for(db, provider: Provider, workflow: str | None) -> None:  # noqa: ANN001
    if provider.type == "comfyui" and not workflow:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="ComfyUI 类型需要指定 workflow（工作流包名）"
        )


@router.post("/generate", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def generate(
    body: ImageGenerateRequest,
    user: CurrentUser,
    db: DbSession,
    request: Request,
    wait: bool = False,
) -> Job:
    provider = pick_provider(db, "image", body.provider_id)
    _validate_workflow_for(db, provider, body.workflow)
    if provider.type != "comfyui" and not body.prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 prompt")

    inputs = {
        "prompt": body.prompt,
        "negative_prompt": body.negative_prompt,
        "width": body.width,
        "height": body.height,
        "seed": body.seed,
        "batch_size": body.n,
        **({"steps": body.steps} if body.steps is not None else {}),
        **body.inputs,
    }
    job = request.app.state.jobs.submit(
        db,
        owner_id=user.id,
        kind="image.generate",
        params={
            "workflow": body.workflow,
            "prompt": body.prompt,
            "size": f"{body.width}x{body.height}",
            "n": body.n,
            "inputs": inputs,
            "options": body.options,
        },
        provider_id=provider.id,
        model=body.model,
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job


@router.post("/edit", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def edit(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    images: Annotated[list[UploadFile], File()],
    prompt: Annotated[str, Form()] = "",
    provider_id: Annotated[int | None, Form()] = None,
    workflow: Annotated[str | None, Form()] = None,
    inputs: Annotated[str, Form()] = "{}",
    wait: bool = False,
) -> Job:
    import json

    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少输入图像")
    provider = pick_provider(db, "image", provider_id)
    _validate_workflow_for(db, provider, workflow)

    image_paths = []
    for upload in images:
        content = await upload.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空文件")
        image_paths.append(save_upload(upload.filename or "image.png", content))

    try:
        extra_inputs = json.loads(inputs)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"inputs JSON 解析失败: {exc}"
        ) from exc

    # 提示词留空时不覆盖包里的默认句（调色包要保留 LoRA 触发词）
    merged_inputs = dict(extra_inputs)
    if prompt.strip():
        merged_inputs["prompt"] = prompt
    job = request.app.state.jobs.submit(
        db,
        owner_id=user.id,
        kind="image.edit",
        params={
            "workflow": workflow,
            "prompt": prompt,
            "image_paths": image_paths,
            "inputs": merged_inputs,
            "options": {
                key: extra_inputs[key]
                for key in ("size", "output_format", "watermark", "sequential_image_generation")
                if key in extra_inputs
            },
        },
        provider_id=provider.id,
        model=str(extra_inputs.get("model") or "") or None,
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job


@router.post("/optimize-prompt", response_model=PromptOptimizeResponse)
async def optimize(
    body: PromptOptimizeRequest, user: CurrentUser, db: DbSession
) -> PromptOptimizeResponse:
    """兼容旧路径；新客户端请用 POST /api/v1/prompts/optimize。"""
    try:
        optimized = await optimize_prompt(db, body.provider_id, body.prompt)
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return PromptOptimizeResponse(optimized=optimized.strip())


def _parse_asset_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in (raw or "").replace("，", ",").split(","):
        text = part.strip()
        if not text:
            continue
        if not text.isdigit():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效的资产 ID：{text}")
        ids.append(int(text))
    return ids


@router.post("/depth", response_model=list[AssetOut])
async def convert_depth(
    user: CurrentUser,
    db: DbSession,
    images: Annotated[list[UploadFile] | None, File()] = None,
    asset_ids: Annotated[str, Form()] = "",
    provider_id: Annotated[int | None, Form()] = None,
    model: Annotated[str, Form()] = "",
    device: Annotated[str, Form()] = "",
) -> list[Asset]:
    """批量把图片转成深度图。产物文件名固定为 <原名>_depth.png。"""
    wanted_device = (device or "").strip().lower()
    if wanted_device and wanted_device not in {"cuda", "cpu"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="device 只能是 cuda 或 cpu")
    items: list[tuple[str, bytes]] = []
    for upload in images or []:
        content = await upload.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空文件")
        items.append((upload.filename or "image.png", content))
    for asset_id in _parse_asset_ids(asset_ids):
        asset = db.get(Asset, asset_id)
        if asset is None or asset.owner_id != user.id or asset.kind != "image":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"找不到图片资产 {asset_id}")
        meta = asset.meta or {}
        source = str(meta.get("source_name") or Path(asset.path).name)
        items.append((source, resolve(asset.path).read_bytes()))
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传图片或选择已有资产")
    if len(items) > 20:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="一次最多转换 20 张")

    provider = pick_provider(db, "depth", provider_id)
    adapter = build_adapter(provider)
    saved: list[Asset] = []
    for filename, content in items:
        try:
            _remote_name, png = await adapter.convert_depth(
                content,
                filename,
                model=model.strip(),
                device=wanted_device,
            )
        except ProviderError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        out_name = depth_output_name(filename)
        rel_path = f"outputs/depth/{uuid.uuid4().hex[:12]}_{out_name}"
        save_bytes(png, rel_path)
        saved.append(
            create_asset(
                db,
                kind="image",
                rel_path=rel_path,
                owner_id=user.id,
                meta={
                    "op": "depth",
                    "source_name": out_name,
                    "name": Path(out_name).stem,
                    "model": model.strip() or None,
                    "provider": provider.name,
                },
            )
        )
    return saved
