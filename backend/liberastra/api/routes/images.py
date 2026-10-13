"""图像路由：文生图、图生图/修复放大（统一为 edit）、提示词优化。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.api.utils import wait_for_job
from liberastra.models import Job, Provider
from liberastra.providers.base import ProviderError
from liberastra.schemas.image import (
    ImageGenerateRequest,
    PromptOptimizeRequest,
    PromptOptimizeResponse,
)
from liberastra.schemas.job import JobOut
from liberastra.services.image import optimize_prompt
from liberastra.services.providers import pick_provider
from liberastra.storage import save_upload

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
        model=None,
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

    job = request.app.state.jobs.submit(
        db,
        owner_id=user.id,
        kind="image.edit",
        params={
            "workflow": workflow,
            "prompt": prompt,
            "image_paths": image_paths,
            "inputs": {"prompt": prompt, **extra_inputs},
        },
        provider_id=provider.id,
        model=None,
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job


@router.post("/optimize-prompt", response_model=PromptOptimizeResponse)
async def optimize(
    body: PromptOptimizeRequest, user: CurrentUser, db: DbSession
) -> PromptOptimizeResponse:
    try:
        optimized = await optimize_prompt(db, body.provider_id, body.prompt)
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return PromptOptimizeResponse(optimized=optimized.strip())
