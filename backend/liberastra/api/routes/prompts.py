"""提示词库与优化 API。"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.api.utils import wait_for_job
from liberastra.models import Job
from liberastra.providers.base import ProviderError
from liberastra.schemas.job import JobOut
from liberastra.services import prompts as prompt_service
from liberastra.services.providers import pick_llm_with_model

router = APIRouter(prefix="/prompts", tags=["prompts"])


class PromptOptimizeRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    task: str = Field(default="t2i", max_length=64)
    scene: str | None = Field(default=None, max_length=64)
    workflow: str | None = Field(default=None, max_length=200)
    aspect: str | None = Field(default=None, max_length=32)
    extra_context: str | None = Field(default=None, max_length=4000)
    provider_id: int | None = None
    model: str = Field(default="", max_length=200)


class PromptOptimizeResponse(BaseModel):
    """兼容旧同步响应；新客户端请用 JobOut。"""

    optimized: str
    provider_name: str = ""
    model: str = ""


class TaskUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    system: str = Field(min_length=1, max_length=50_000)
    capabilities: list[str] = Field(default_factory=list)


class SceneUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    append: str = Field(default="", max_length=20_000)


class PromptImportBody(BaseModel):
    tasks: dict[str, Any] | None = None
    scenes: dict[str, Any] | None = None


@router.get("")
def list_prompts(user: CurrentUser) -> dict[str, Any]:
    """列出可用 task / scene 模板（内置 + 用户覆盖）。"""
    prompt_service.ensure_prompt_store()
    return {"tasks": prompt_service.list_tasks(), "scenes": prompt_service.list_scenes()}


@router.put("/tasks/{task_id}")
def put_task(task_id: str, body: TaskUpsert, user: CurrentUser) -> dict[str, str]:
    prompt_service.upsert_task(
        task_id, name=body.name, system=body.system, capabilities=body.capabilities
    )
    return {"status": "ok", "id": task_id}


@router.put("/scenes/{scene_id}")
def put_scene(scene_id: str, body: SceneUpsert, user: CurrentUser) -> dict[str, str]:
    prompt_service.upsert_scene(scene_id, name=body.name, append=body.append)
    return {"status": "ok", "id": scene_id}


@router.post("/import")
def import_prompts(body: PromptImportBody, user: CurrentUser) -> dict[str, int]:
    return prompt_service.import_prompts(body.model_dump(exclude_none=True))


@router.post("/optimize", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def optimize(
    body: PromptOptimizeRequest,
    user: CurrentUser,
    db: DbSession,
    request: Request,
    wait: bool = False,
) -> Job:
    """提交 prompt.optimize Job；`?wait=true` 时同步等到终态。"""
    try:
        provider, resolved_model = pick_llm_with_model(db, body.provider_id, body.model)
    except HTTPException:
        raise
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    prompt_service.ensure_prompt_store()
    job = request.app.state.jobs.submit(
        db,
        owner_id=user.id,
        kind="prompt.optimize",
        params={
            "prompt": body.prompt,
            "task": body.task,
            "scene": body.scene,
            "workflow": body.workflow,
            "aspect": body.aspect,
            "extra_context": body.extra_context,
        },
        provider_id=provider.id,
        model=resolved_model,
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job


@router.post("/optimize/stream")
async def optimize_stream(
    body: PromptOptimizeRequest, user: CurrentUser, db: DbSession, request: Request
) -> EventSourceResponse:
    """SSE 流式优化（调试/兼容）。新 UI 请用 POST /optimize + Job 轮询。"""

    async def events() -> AsyncGenerator[dict[str, str], None]:
        try:
            async for item in prompt_service.optimize_prompt_stream(
                db,
                prompt=body.prompt,
                task=body.task,
                scene=body.scene,
                workflow=body.workflow,
                aspect=body.aspect,
                extra_context=body.extra_context,
                provider_id=body.provider_id,
                model=body.model,
            ):
                if await request.is_disconnected():
                    return
                event = str(item.get("event", "message"))
                payload = {k: v for k, v in item.items() if k != "event"}
                yield {"event": event, "data": json.dumps(payload, ensure_ascii=False)}
                if event in ("done", "error"):
                    return
        except ProviderError as exc:
            yield {
                "event": "error",
                "data": json.dumps({"message": str(exc)}, ensure_ascii=False),
            }
        except Exception as exc:  # noqa: BLE001
            yield {
                "event": "error",
                "data": json.dumps(
                    {"message": f"提示词优化失败: {exc}"}, ensure_ascii=False
                ),
            }

    return EventSourceResponse(events())
