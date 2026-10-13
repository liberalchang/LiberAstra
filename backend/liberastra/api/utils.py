"""API 层公共工具：等待 Job 进入终态。"""

from __future__ import annotations

import asyncio

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from liberastra.models import Job
from liberastra.models.job import TERMINAL_STATUSES

WAIT_TIMEOUT_SECONDS = 300.0


async def wait_for_job(db: Session, job_id: str, timeout: float = WAIT_TIMEOUT_SECONDS) -> Job:
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
