"""LLM 路由：聊天（走 Job 队列，`?wait=true` 同步等待）。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.models import Job
from liberastra.models.job import TERMINAL_STATUSES
from liberastra.schemas.job import JobOut
from liberastra.schemas.llm import ChatRequest
from liberastra.services.llm import pick_llm_provider

router = APIRouter(prefix="/llm", tags=["llm"])

WAIT_TIMEOUT_SECONDS = 300.0


async def _wait_for_job(db: Session, job_id: str, timeout: float = WAIT_TIMEOUT_SECONDS) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    elapsed = 0.0
    while elapsed < timeout:
        db.refresh(job)  # 绕过 identity map 缓存，读取 worker 的最新写入
        if job.status in TERMINAL_STATUSES:
            return job
        await asyncio.sleep(0.5)
        elapsed += 0.5
    raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="等待任务完成超时")


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
        return await _wait_for_job(db, job.id)
    return job
