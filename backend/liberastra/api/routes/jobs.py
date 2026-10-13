"""Job 路由：列表、详情、取消、重试、SSE 进度推送。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sse_starlette import EventSourceResponse

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.jobs.manager import JobManager
from liberastra.models import Job, User
from liberastra.models.job import TERMINAL_STATUSES
from liberastra.schemas.job import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_manager(request: Request) -> JobManager:
    return request.app.state.jobs  # type: ignore[no-any-return]


def _get_owned(db, job_id: str, user: User) -> Job:  # noqa: ANN001
    job = db.get(Job, job_id)
    if job is None or job.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return job


@router.get("", response_model=list[JobOut])
def list_jobs(
    user: CurrentUser,
    db: DbSession,
    status_filter: str | None = None,
    kind: str | None = None,
    limit: int = 50,
) -> list[Job]:
    stmt = select(Job).where(Job.owner_id == user.id).order_by(Job.created_at.desc())
    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    if kind:
        stmt = stmt.where(Job.kind == kind)
    return list(db.scalars(stmt.limit(min(limit, 200))).all())


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: CurrentUser, db: DbSession) -> Job:
    return _get_owned(db, job_id, user)


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, user: CurrentUser, db: DbSession, request: Request) -> Job:
    job = _get_owned(db, job_id, user)
    if not _get_manager(request).request_cancel(db, job):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="任务已结束，无法取消"
        )
    db.refresh(job)
    return job


@router.post("/{job_id}/retry", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def retry_job(job_id: str, user: CurrentUser, db: DbSession, request: Request) -> Job:
    job = _get_owned(db, job_id, user)
    if job.status not in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="任务进行中，不能重试"
        )
    return _get_manager(request).submit(
        db,
        owner_id=user.id,
        kind=job.kind,
        params=job.params,
        provider_id=job.provider_id,
        model=job.model,
    )


@router.get("/{job_id}/events")
async def job_events(job_id: str, user: CurrentUser, db: DbSession, request: Request):
    """SSE：连接即推送当前快照，随后推送每次状态变化，终态后关闭。"""
    job = _get_owned(db, job_id, user)
    snapshot = JobOut.model_validate(job).model_dump(mode="json")
    manager = _get_manager(request)
    queue = manager.subscribe(job_id)

    async def stream() -> AsyncGenerator[dict, None]:
        try:
            yield {"event": "status", "data": json.dumps(snapshot)}
            if snapshot["status"] in TERMINAL_STATUSES:
                return
            while True:
                if await request.is_disconnected():
                    return
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield {"comment": "ping"}
                    continue
                yield {"event": "status", "data": json.dumps(payload["job"])}
                if payload["job"]["status"] in TERMINAL_STATUSES:
                    return
        finally:
            manager.unsubscribe(job_id, queue)

    return EventSourceResponse(stream())
