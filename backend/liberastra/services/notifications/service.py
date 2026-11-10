"""终态通知入队：按规则匹配渠道，写入 outbox。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
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
from liberastra.services.notifications.render import (
    elapsed_text,
    render_canvas_run,
    render_terminal,
)
from liberastra.services.preferences import get_str_pref


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _kind_matches(rule: NotificationRule, job: Job) -> bool:
    kinds = list(rule.job_kinds or [])
    params = job.params or {}
    is_canvas_child = bool(params.get("canvas_id") and params.get("node_id"))
    if is_canvas_child and job.kind not in kinds:
        return False
    return not kinds or job.kind in kinds


def _apply_template(template: str | None, title: str, body: str, job: Job, link: str | None) -> str:
    if not template:
        return body
    values = {
        "job_name": title,
        "status": job.status,
        "progress": f"{round((job.progress or 0) * 100)}%",
        "elapsed": elapsed_text(job),
        "error": job.error or "",
        "link": link or "",
        "outputs": str(len(job.outputs or [])),
    }
    text = template
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def enqueue_terminal_for_job(db: Session, job: Job) -> int:
    """为一条终态 Job 写投递记录；返回新增条数。"""
    if job.status not in TERMINAL_STATUSES:
        return 0
    event = f"job.{job.status}"
    rules = db.scalars(
        select(NotificationRule).where(
            NotificationRule.owner_id == job.owner_id,
            NotificationRule.enabled.is_(True),
        )
    ).all()
    language = get_str_pref(db, "notification_language")
    base_url = get_str_pref(db, "notification_public_base_url") or None
    finished = _utc(job.finished_at)
    created = 0
    for rule in rules:
        if event not in (rule.events or []):
            continue
        if not _kind_matches(rule, job):
            continue
        since = _utc(rule.enabled_since)
        if finished is not None and since is not None and finished < since:
            continue
        channels = db.scalars(
            select(NotificationChannel)
            .join(
                NotificationRuleChannel,
                NotificationRuleChannel.channel_id == NotificationChannel.id,
            )
            .where(
                NotificationRuleChannel.rule_id == rule.id,
                NotificationChannel.owner_id == job.owner_id,
                NotificationChannel.enabled.is_(True),
            )
        ).all()
        if not channels:
            continue
        message = (
            render_canvas_run(
                job, language, base_url, include_outputs=rule.include_outputs
            )
            if job.kind == "canvas.run"
            else render_terminal(
                job, language, base_url, include_outputs=rule.include_outputs
            )
        )
        template = {
            "succeeded": rule.template_succeeded,
            "failed": rule.template_failed,
        }.get(job.status)
        body = _apply_template(template, message.title, message.body, job, message.link)
        for channel in channels:
            delivery = NotificationDelivery(
                owner_id=job.owner_id,
                rule_id=rule.id,
                channel_id=channel.id,
                job_id=job.id,
                event=event,
                bucket=job.status,
                dedup_key=f"job:{job.id}:{event}:rule:{rule.id}:channel:{channel.id}",
                title=message.title[:255],
                body=body,
                payload={**message.payload, "link": message.link},
                status="pending",
                attempts=0,
                max_attempts=channel.max_attempts,
                next_attempt_at=utcnow(),
            )
            try:
                with db.begin_nested():
                    db.add(delivery)
            except IntegrityError:
                continue
            created += 1
    if created:
        db.commit()
    return created


def enqueue_terminal(job_id: str) -> int:
    """供 JobManager / 画布汇总使用：独立 Session，失败不影响任务。"""
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return 0
        return enqueue_terminal_for_job(db, job)
    finally:
        db.close()
