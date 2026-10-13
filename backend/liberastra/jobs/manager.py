"""持久化异步任务队列：SQLite jobs 表 + asyncio worker。

- 按 Provider 限制并发（Provider.concurrency），另有全局并发上限。
- 进度通过 `_emit` 推送给 SSE 订阅者；同步接口只是“提交后轮询等待”。
- 取消为协作式：running 中的任务在下一个检查点生效。
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from liberastra.core.db import SessionLocal
from liberastra.models import Job, utcnow
from liberastra.models.job import TERMINAL_STATUSES
from liberastra.schemas.job import JobOut

RunnerFactory = Callable[["Session", Job, "JobContext"], Awaitable[list[dict[str, Any]]]]


class JobContext:
    """传给 runner 的上下文：进度上报与取消检查。"""

    def __init__(self, manager: JobManager, job_id: str) -> None:
        self._manager = manager
        self.job_id = job_id

    def cancelled(self) -> bool:
        return self._manager.is_cancelled(self.job_id)

    def report(
        self,
        db: Session,
        job: Job,
        *,
        progress: float | None = None,
        step: str | None = None,
    ) -> None:
        if progress is not None:
            job.progress = progress
        if step is not None:
            job.steps = [*job.steps, {"name": step, "at": utcnow().isoformat()}]
        job.updated_at = utcnow()
        db.commit()
        self._manager.emit(job)


class JobManager:
    def __init__(self, global_concurrency: int = 4) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._cancellations: set[str] = set()
        self._provider_limits: dict[int, int] = {}
        self._semaphores: dict[int, asyncio.Semaphore] = {}
        self._global_sem: asyncio.Semaphore | None = None
        self._global_concurrency = global_concurrency
        self._runners: dict[str, RunnerFactory] = {}
        self._worker_task: asyncio.Task | None = None
        self._running: dict[str, asyncio.Task] = {}

    # ---- 注册与生命周期 ----

    def register(self, kind: str, factory: RunnerFactory) -> None:
        self._runners[kind] = factory

    def set_provider_limit(self, provider_id: int, limit: int) -> None:
        self._provider_limits[provider_id] = limit
        self._semaphores.pop(provider_id, None)  # 下次使用时按新上限重建

    def start(self) -> None:
        if self._worker_task is None:
            self._global_sem = asyncio.Semaphore(self._global_concurrency)
            self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            self._worker_task = None
        for task in self._running.values():
            task.cancel()
        if self._running:
            await asyncio.gather(*self._running.values(), return_exceptions=True)
        self._running.clear()

    # ---- 提交与取消 ----

    def submit(
        self,
        db: Session,
        *,
        owner_id: int,
        kind: str,
        params: dict,
        provider_id: int | None = None,
        model: str | None = None,
    ) -> Job:
        job = Job(kind=kind, params=params, provider_id=provider_id, model=model, owner_id=owner_id)
        db.add(job)
        db.commit()
        db.refresh(job)
        self._queue.put_nowait(job.id)
        return job

    def request_cancel(self, db: Session, job: Job) -> bool:
        if job.status == "pending":
            job.status = "canceled"
            job.finished_at = utcnow()
            db.commit()
            self.emit(job)
            return True
        if job.status == "running":
            self._cancellations.add(job.id)
            return True
        return False

    def is_cancelled(self, job_id: str) -> bool:
        return job_id in self._cancellations

    # ---- worker ----

    async def _worker(self) -> None:
        while True:
            job_id = await self._queue.get()
            task = asyncio.create_task(self._run(job_id))
            self._running[job_id] = task
            task.add_done_callback(lambda _t, jid=job_id: self._running.pop(jid, None))

    def _semaphore_for(self, provider_id: int | None) -> asyncio.Semaphore | None:
        if provider_id is None:
            return None
        if provider_id not in self._semaphores:
            self._semaphores[provider_id] = asyncio.Semaphore(
                self._provider_limits.get(provider_id, 2)
            )
        return self._semaphores[provider_id]

    async def _run(self, job_id: str) -> None:
        assert self._global_sem is not None
        async with self._global_sem:
            db = SessionLocal()
            sem: asyncio.Semaphore | None = None
            try:
                job = db.get(Job, job_id)
                if job is None or job.status != "pending":
                    return
                if job_id in self._cancellations:
                    self._finish(db, job, "canceled")
                    return
                sem = self._semaphore_for(job.provider_id)
                if sem is not None:
                    await sem.acquire()
                try:
                    job.status = "running"
                    job.updated_at = utcnow()
                    db.commit()
                    self.emit(job)

                    factory = self._runners.get(job.kind)
                    if factory is None:
                        raise RuntimeError(f"未注册的任务类型: {job.kind}")
                    outputs = await factory(db, job, JobContext(self, job_id))

                    db.refresh(job)
                    if job_id in self._cancellations:
                        self._finish(db, job, "canceled")
                    else:
                        job.outputs = outputs
                        job.progress = 1.0
                        self._finish(db, job, "succeeded")
                except asyncio.CancelledError:
                    db.rollback()
                    job = db.get(Job, job_id)
                    if job is not None:
                        self._finish(db, job, "canceled")
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.exception("任务 {} 失败", job_id)
                    db.rollback()
                    job = db.get(Job, job_id)
                    if job is not None:
                        job.error = str(exc)[:2000]
                        self._finish(db, job, "failed")
                finally:
                    if sem is not None:
                        sem.release()
                    self._cancellations.discard(job_id)
            finally:
                db.close()

    def _finish(self, db: Session, job: Job, status: str) -> None:
        job.status = status
        job.updated_at = utcnow()
        if status in TERMINAL_STATUSES:
            job.finished_at = utcnow()
        db.commit()
        self.emit(job)

    # ---- SSE 订阅 ----

    def emit(self, job: Job) -> None:
        queues = self._subscribers.get(job.id)
        if not queues:
            return
        payload = {"type": "status", "job": JobOut.model_validate(job).model_dump(mode="json")}
        for queue in queues:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:  # 慢消费者丢弃中间帧，终态总会送达
                pass

    def subscribe(self, job_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[job_id].add(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        queues = self._subscribers.get(job_id)
        if queues is not None:
            queues.discard(queue)
            if not queues:
                self._subscribers.pop(job_id, None)
