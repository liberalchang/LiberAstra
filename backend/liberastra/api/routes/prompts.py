"""提示词库与优化 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.providers.base import ProviderError
from liberastra.services import prompts as prompt_service

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


@router.post("/optimize", response_model=PromptOptimizeResponse)
async def optimize(body: PromptOptimizeRequest, user: CurrentUser, db: DbSession) -> PromptOptimizeResponse:
    try:
        result = await prompt_service.optimize_prompt(
            db,
            prompt=body.prompt,
            task=body.task,
            scene=body.scene,
            workflow=body.workflow,
            aspect=body.aspect,
            extra_context=body.extra_context,
            provider_id=body.provider_id,
            model=body.model,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return PromptOptimizeResponse(**result)
