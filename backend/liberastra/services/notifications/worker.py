"""通知 outbox worker、进度调度、terminal sweep 和清理。"""

from __future__ import annotations

import asyncio
import os
import socket
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from liberastra.core.db import SessionLocal
from liberastra.models import (
    Job,
    NotificationChannel,
    NotificationDelivery,
    NotificationRule,
    NotificationRuleChannel,
    utcnow,
)
from liberastra.models.job import TERMINAL_STATUSES
from liberastra.services.notifications.adapters import NotificationMessage, send
from liberastra.services.notifications.config import ConfigError, decrypt_config
from liberastra.services.notifications.render import (
    ProgressEntry,
    format_elapsed,
    job_name,
    render_progress,
)
from liberastra.services.notifications.service import enqueue_terminal_for_job
from liberastra.services.preferences import get_str_pref

LEASE_SECONDS = 120
RETRY_CAP_SECONDS = 3600
TERMINAL_SWEEP_SECONDS = 6 * 3600
CLEANUP_SECONDS = 24 * 3600
RETENTION_DAYS = 30


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _retryable(result_status: int | None) -> bool:
    return result_status is None or result_status >= 500 or result_status in (408, 429)


def _step_label(job: Job) -> str:
    steps = job.steps or []
    if not steps:
        return ""
    last = steps[-1]
    if isinstance(last, dict):
        return str(last.get("label") or last.get("name") or last.get("step") or "")[:60]
    return str(last)[:60]


def _quiet_now(rule: NotificationRule, now: datetime) -> bool:
    value = rule.quiet_hours or {}
    if not value:
        return False
    try:
        tz = ZoneInfo(str(value.get("timezone") or "UTC"))
        start = time.fromisoformat(str(value.get("start")))
        end = time.fromisoformat(str(value.get("end")))
    except (ValueError, KeyError):
        return False
    local = now.astimezone(tz).time()
    if start <= end:
        return start <= local < end
    return local >= start or local < end


class NotificationWorker:
    def __init__(self, worker_id: str | None = None) -> None:
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
        self._stopped = asyncio.Event()

    def stop(self) -> None:
        self._stopped.set()

    async def run(self) -> None:
        while not self._stopped.is_set():
            try:
                sent = await self._send_once()
            except Exception:  # noqa: BLE001
                logger.exception("通知 worker 异常")
                sent = False
            if not sent:
                try:
                    await asyncio.wait_for(self._stopped.wait(), timeout=5)
                except TimeoutError:
                    pass

    def _reset_stale(self, db: Session, now: datetime) -> None:
        cutoff = now - timedelta(seconds=LEASE_SECONDS)
        db.execute(
            update(NotificationDelivery)
            .where(
                NotificationDelivery.status == "sending",
                NotificationDelivery.locked_at.is_not(None),
                NotificationDelivery.locked_at < cutoff,
            )
            .values(status="pending", locked_at=None, locked_by=None)
        )
        db.commit()

    def _claim(self, db: Session, now: datetime) -> int | None:
        cutoff = now - timedelta(seconds=LEASE_SECONDS)
        candidate = (
            select(NotificationDelivery.id)
            .where(
                NotificationDelivery.status == "pending",
                or_(
                    NotificationDelivery.next_attempt_at.is_(None),
                    NotificationDelivery.next_attempt_at <= now,
                ),
                or_(
                    NotificationDelivery.locked_at.is_(None),
                    NotificationDelivery.locked_at < cutoff,
                ),
            )
            .order_by(NotificationDelivery.id)
            .limit(1)
            .scalar_subquery()
        )
        stmt = (
            update(NotificationDelivery)
            .where(
                NotificationDelivery.id == candidate,
                NotificationDelivery.status == "pending",
            )
            .values(status="sending", locked_at=now, locked_by=self.worker_id)
            .returning(NotificationDelivery.id)
        )
        claimed = db.scalar(stmt)
        db.commit()
        return int(claimed) if claimed is not None else None

    async def _send_once(self) -> bool:
        db = SessionLocal()
        try:
            now = utcnow()
            self._reset_stale(db, now)
            delivery_id = self._claim(db, now)
            if delivery_id is None:
                return False
            delivery = db.get(NotificationDelivery, delivery_id)
            if delivery is None:
                return True
            if delivery.channel_id is None or delivery.rule_id is None:
                delivery.status = "skipped"
                delivery.last_error = "规则或渠道已删除"
                db.commit()
                return True
            rule = db.get(NotificationRule, delivery.rule_id)
            if rule is None or not rule.enabled:
                delivery.status = "skipped"
                delivery.last_error = "规则不存在或已停用"
                db.commit()
                return True
            channel = db.get(NotificationChannel, delivery.channel_id)
            if channel is None or not channel.enabled:
                delivery.status = "skipped"
                delivery.last_error = "渠道不存在或已停用"
                db.commit()
                return True
            try:
                config = decrypt_config(channel.config_encrypted)
            except ConfigError as exc:
                delivery.status = "failed"
                delivery.attempts += 1
                delivery.last_error = str(exc)
                delivery.locked_at = None
                delivery.locked_by = None
                db.commit()
                return True
            payload = delivery.payload or {}
            message = NotificationMessage(
                title=delivery.title,
                body=delivery.body,
                event=delivery.event,
                job_id=delivery.job_id,
                link=payload.get("link"),
                delivery_id=delivery.id,
                payload=payload,
            )
            proxy = get_str_pref(db, "notification_proxy") or None
            use_proxy = bool(config.get("use_proxy", True))
            result = await send(
                channel.type,
                config,
                message,
                timeout=float(channel.timeout_seconds),
                proxy=proxy if use_proxy else None,
                use_proxy=use_proxy,
            )
            delivery.attempts += 1
            delivery.response_status = result.status
            delivery.locked_at = None
            delivery.locked_by = None
            if result.ok:
                delivery.status = "sent"
                delivery.sent_at = utcnow()
                delivery.last_error = None
                channel.last_error = None
            else:
                delivery.last_error = result.message
                channel.last_error = result.message
                if delivery.attempts >= delivery.max_attempts or not _retryable(result.status):
                    delivery.status = "failed"
                    delivery.next_attempt_at = None
                else:
                    if result.retry_after is not None:
                        backoff = min(max(1.0, result.retry_after), RETRY_CAP_SECONDS)
                    else:
                        backoff = min(
                            channel.backoff_seconds
                            * (2 ** max(0, delivery.attempts - 1)),
                            RETRY_CAP_SECONDS,
                        )
                    delivery.status = "pending"
                    delivery.next_attempt_at = utcnow() + timedelta(seconds=backoff)
            db.commit()
            return True
        finally:
            db.close()


class NotificationScheduler:
    def __init__(self) -> None:
        self._stopped = asyncio.Event()
        self._next_sweep = 0.0
        self._next_cleanup = 0.0

    def stop(self) -> None:
        self._stopped.set()

    async def run(self) -> None:
        while not self._stopped.is_set():
            try:
                loop = asyncio.get_running_loop()
                now = loop.time()
                with SessionLocal() as db:
                    if now >= self._next_sweep:
                        self.terminal_sweep(db)
                        self._next_sweep = now + TERMINAL_SWEEP_SECONDS
                    if now >= self._next_cleanup:
                        self.cleanup(db)
                        self._next_cleanup = now + CLEANUP_SECONDS
                    self.progress_tick(db)
            except Exception:  # noqa: BLE001
                logger.exception("通知调度器异常")
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=30)
            except TimeoutError:
                pass

    def terminal_sweep(self, db: Session) -> int:
        since = utcnow() - timedelta(hours=24)
        jobs = db.scalars(
            select(Job).where(
                Job.status.in_(TERMINAL_STATUSES),
                Job.finished_at.is_not(None),
                Job.finished_at >= since,
            )
        ).all()
        created = 0
        for job in jobs:
            try:
                created += enqueue_terminal_for_job(db, job)
            except Exception:  # noqa: BLE001
                logger.exception("terminal sweep 入队失败 job={}", job.id)
        return created

    def cleanup(self, db: Session) -> int:
        cutoff = utcnow() - timedelta(days=RETENTION_DAYS)
        result = db.execute(
            delete(NotificationDelivery).where(
                NotificationDelivery.status.in_(("sent", "failed", "skipped")),
                NotificationDelivery.created_at < cutoff,
            )
        )
        db.commit()
        return int(result.rowcount or 0)

    def progress_tick(self, db: Session) -> int:
        now = utcnow()
        rules = db.scalars(
            select(NotificationRule).where(NotificationRule.enabled.is_(True))
        ).all()
        created = 0
        for rule in rules:
            if "job.progress" not in (rule.events or []):
                continue
            if rule.progress_interval_seconds <= 0 or _quiet_now(rule, now):
                continue
            jobs = db.scalars(
                select(Job).where(
                    Job.owner_id == rule.owner_id,
                    Job.status.in_(("pending", "running")),
                )
            ).all()
            kinds = list(rule.job_kinds or [])
            selected: list[Job] = []
            for job in jobs:
                params = job.params or {}
                is_canvas_child = bool(params.get("canvas_id") and params.get("node_id"))
                if is_canvas_child and "canvas.node" not in kinds:
                    continue
                if kinds and job.kind not in kinds:
                    continue
                selected.append(job)
            if not selected:
                continue
            running = sum(1 for job in selected if job.status == "running")
            queued = sum(1 for job in selected if job.status == "pending")
            selected.sort(key=lambda job: job.created_at)
            entries = [
                ProgressEntry(
                    name=(
                        str((job.params or {}).get("canvas_name") or job_name(job))
                        if job.kind == "canvas.run"
                        else job_name(job)
                    ),
                    progress=float(job.progress or 0),
                    step=_step_label(job),
                    elapsed=format_elapsed(_utc(job.created_at), now),
                )
                for job in selected[: rule.max_jobs_per_digest]
            ]
            hidden = max(0, len(selected) - len(entries))
            message = render_progress(
                entries,
                get_str_pref(db, "notification_language"),
                get_str_pref(db, "notification_public_base_url") or None,
                running=running,
                queued=queued,
                hidden=hidden,
            )
            body = message.body
            if rule.template_progress:
                body = (
                    rule.template_progress.replace("{count}", str(len(selected)))
                    .replace("{running}", str(running))
                    .replace("{queued}", str(queued))
                    .replace("{jobs}", message.body)
                    .replace("{link}", message.link or "")
                )
            bucket = int(now.timestamp() // rule.progress_interval_seconds)
            channels = db.scalars(
                select(NotificationChannel)
                .join(
                    NotificationRuleChannel,
                    NotificationRuleChannel.channel_id == NotificationChannel.id,
                )
                .where(
                    NotificationRuleChannel.rule_id == rule.id,
                    NotificationChannel.owner_id == rule.owner_id,
                    NotificationChannel.enabled.is_(True),
                )
            ).all()
            for channel in channels:
                delivery = NotificationDelivery(
                    owner_id=rule.owner_id,
                    rule_id=rule.id,
                    channel_id=channel.id,
                    job_id=None,
                    event="job.progress",
                    bucket=str(bucket),
                    dedup_key=(
                        f"progress:{rule.owner_id}:{rule.id}:"
                        f"{rule.progress_interval_seconds}:{bucket}:channel:{channel.id}"
                    ),
                    title=message.title[:255],
                    body=body,
                    payload={**message.payload, "link": message.link},
                    status="pending",
                    attempts=0,
                    max_attempts=channel.max_attempts,
                    next_attempt_at=now,
                )
                try:
                    with db.begin_nested():
                        db.add(delivery)
                except IntegrityError:
                    continue
                created += 1
            db.commit()
        return created
