"""LLM 路由：聊天（走 Job 队列，`?wait=true` 同步等待）。"""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.api.utils import wait_for_job
from liberastra.models import Job
from liberastra.schemas.job import JobOut
from liberastra.schemas.llm import ChatRequest
from liberastra.services.llm import pick_llm_provider

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/chat", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def chat(
    body: ChatRequest,
    user: CurrentUser,
    db: DbSession,
    request: Request,
    wait: bool = False,
) -> Job:
    provider = pick_llm_provider(db, body.provider_id)
    job = request.app.state.jobs.submit(
        db,
        owner_id=user.id,
        kind="llm.chat",
        params={"messages": body.messages, "options": body.options},
        provider_id=provider.id,
        model=body.model,
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job
