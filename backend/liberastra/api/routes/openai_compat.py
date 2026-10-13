"""OpenAI 兼容子集（/v1）：chat/completions、images/generations。

同步代理到默认 Provider，便于现有 Agent 与 SDK 直接接入。
"""

from __future__ import annotations

import base64
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.providers.base import ProviderError
from liberastra.services.providers import build_image_adapter, build_llm_adapter, pick_provider

router = APIRouter(prefix="/v1", tags=["openai-compat"])


class ChatCompletionRequest(BaseModel):
    model: str = "default"
    messages: list[dict[str, Any]] = Field(min_length=1)
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False


@router.post("/chat/completions")
async def chat_completions(body: ChatCompletionRequest, user: CurrentUser, db: DbSession) -> dict:
    if body.stream:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="暂不支持 stream，请置 false"
        )
    provider = pick_provider(db, "llm")
    adapter = build_llm_adapter(provider)
    options = {
        k: v
        for k, v in {"temperature": body.temperature, "max_tokens": body.max_tokens}.items()
        if v is not None
    }
    try:
        content = await adapter.chat(
            model=body.model if body.model != "default" else provider.extra.get("model", "default"),
            messages=body.messages,
            **options,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


class ImagesGenerationRequest(BaseModel):
    model: str | None = None
    prompt: str = Field(min_length=1)
    n: int = Field(default=1, ge=1, le=8)
    size: str = "1024x1024"
    response_format: str = Field(default="b64_json", pattern="^(b64_json|url)$")


@router.post("/images/generations")
async def images_generations(body: ImagesGenerationRequest, user: CurrentUser, db: DbSession) -> dict:
    # /v1/images/generations 不支持工作流参数，跳过 comfyui 类型，选在线图像 Provider
    from sqlalchemy import select

    from liberastra.models import Provider

    provider = None
    for record in db.scalars(select(Provider).where(Provider.enabled.is_(True))).all():
        if "image" in record.capabilities and record.type != "comfyui":
            provider = record
            break
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有可用的在线图像 Provider（ComfyUI 请走 /api/v1/images/generate）",
        )
    adapter = build_image_adapter(provider)
    try:
        images = await adapter.generate(
            prompt=body.prompt, size=body.size, n=body.n, model=body.model
        )
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    data: list[dict[str, str]] = []
    for _filename, content in images:
        if body.response_format == "b64_json":
            data.append({"b64_json": base64.b64encode(content).decode()})
        else:
            asset = _save_temp_asset(db, user.id, content)
            data.append({"url": f"/api/v1/assets/{asset}/content"})
    return {"created": int(time.time()), "data": data}


def _save_temp_asset(db, owner_id: int, content: bytes) -> int:  # noqa: ANN001
    from liberastra.storage import create_asset, save_bytes

    rel = f"outputs/openai/{uuid.uuid4().hex}.png"
    save_bytes(content, rel)
    asset = create_asset(db, kind="image", rel_path=rel, owner_id=owner_id, meta={"via": "/v1"})
    return asset.id
