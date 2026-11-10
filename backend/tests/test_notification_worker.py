"""通知 outbox/service/scheduler 的集成测试。"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import delete, select

from liberastra.core.db import SessionLocal
from liberastra.core.security import hash_password
from liberastra.models import (
    Canvas,
    Job,
    NotificationChannel,
    NotificationDelivery,
    NotificationRule,
    NotificationRuleChannel,
    User,
    utcnow,
)
from liberastra.services.canvas_run import _create_run_summary, _finalize_run
from liberastra.services.notifications.adapters import SendResult
from liberastra.services.notifications.config import encrypt_config, validate_config
from liberastra.services.notifications.service import enqueue_terminal_for_job
from liberastra.services.notifications.worker import NotificationScheduler, NotificationWorker


def _new_user(db) -> User:  # noqa: ANN001
    user = User(username=f"notify-{uuid4().hex[:8]}", password_hash=hash_password("secret-123"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _new_channel(db, owner_id: int, name: str = "hook") -> NotificationChannel:  # noqa: ANN001
    channel = NotificationChannel(
        owner_id=owner_id,
        type="webhook",
        name=name,
        config_encrypted=encrypt_config(
            validate_config("webhook", {"url": "https://example.test/hook"})
        ),
        config_version=1,
        enabled=True,
        max_attempts=3,
        backoff_seconds=30,
        timeout_seconds=10,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


def _new_rule(
    db,  # noqa: ANN001
    owner_id: int,
    channel_id: int,
    *,
    events: list[str] | None = None,
    job_kinds: list[str] | None = None,
    interval: int = 3600,
    quiet_hours: dict | None = None,
) -> NotificationRule:
    rule = NotificationRule(
        owner_id=owner_id,
        name=f"rule-{uuid4().hex[:8]}",
        enabled=True,
        enabled_since=utcnow() - timedelta(hours=1),
        events=events or ["job.succeeded", "job.failed"],
        progress_interval_seconds=interval,
        job_kinds=job_kinds or [],
        max_jobs_per_digest=10,
        quiet_hours=quiet_hours,
        include_outputs=True,
    )
    db.add(rule)
    db.flush()
    db.add(NotificationRuleChannel(rule_id=rule.id, channel_id=channel_id))
    db.commit()
    db.refresh(rule)
    return rule


def _new_job(
    db,  # noqa: ANN001
    owner_id: int,
    *,
    kind: str = "video.motion",
    status: str = "succeeded",
    params: dict | None = None,
    job_id: str | None = None,
) -> Job:
    now = utcnow()
    job = Job(
        id=job_id or str(uuid4()),
        kind=kind,
        status=status,
        progress=1.0 if status in ("succeeded", "failed", "canceled") else 0.5,
        owner_id=owner_id,
        params=params or {"node_label": "动作迁移"},
        outputs=[],
        created_at=now - timedelta(minutes=5),
        updated_at=now,
        finished_at=now if status in ("succeeded", "failed", "canceled") else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_terminal_enqueue_dedup_and_canvas_skip(auth_header: dict[str, str]) -> None:
    with SessionLocal() as db:
        user = _new_user(db)
        channel = _new_channel(db, user.id)
        rule = _new_rule(db, user.id, channel.id)
        job = _new_job(db, user.id, params={"node_label": "动作迁移"})
        assert enqueue_terminal_for_job(db, job) == 1
        assert enqueue_terminal_for_job(db, job) == 0
        delivery = db.scalar(
            select(NotificationDelivery).where(NotificationDelivery.job_id == job.id)
        )
        assert delivery is not None
        assert delivery.status == "pending"
        assert "动作迁移" in delivery.title
        assert delivery.rule_id == rule.id

        child = _new_job(
            db,
            user.id,
            kind="canvas.node",
            params={"canvas_id": "c1", "node_id": "n1", "node_label": "节点"},
        )
        assert enqueue_terminal_for_job(db, child) == 0
        rule.job_kinds = ["canvas.node"]
        db.commit()
        assert enqueue_terminal_for_job(db, child) == 1


def test_canvas_run_summary_enqueue(auth_header: dict[str, str]) -> None:
    with SessionLocal() as db:
        user = _new_user(db)
        channel = _new_channel(db, user.id)
        _new_rule(db, user.id, channel.id)
        job = _new_job(
            db,
            user.id,
            kind="canvas.run",
            params={
                "canvas_id": "canvas-1",
                "canvas_name": "测试画布",
                "synthetic": True,
                "success_count": 3,
                "failed_count": 1,
                "duration_ms": 5000,
                "output_count": 2,
            },
        )
        assert enqueue_terminal_for_job(db, job) == 1
        delivery = db.scalar(
            select(NotificationDelivery).where(NotificationDelivery.job_id == job.id)
        )
        assert delivery is not None
        assert "测试画布" in delivery.title
        assert "成功 3" in delivery.body


def test_worker_claim_send_and_retry(monkeypatch, auth_header: dict[str, str]) -> None:
    with SessionLocal() as db:
        db.execute(delete(NotificationDelivery).where(NotificationDelivery.status == "pending"))
        db.commit()
        user = _new_user(db)
        channel = _new_channel(db, user.id)
        _new_rule(db, user.id, channel.id)
        job = _new_job(db, user.id)
        enqueue_terminal_for_job(db, job)
        delivery = db.scalar(
            select(NotificationDelivery).where(NotificationDelivery.job_id == job.id)
        )
        assert delivery is not None

    async def ok_send(*args, **kwargs):  # noqa: ANN002, ANN003
        return SendResult(True, 200, "ok")

    monkeypatch.setattr("liberastra.services.notifications.worker.send", ok_send)
    worker = NotificationWorker("test-worker")
    assert asyncio.run(worker._send_once()) is True
    with SessionLocal() as db:
        sent = db.get(NotificationDelivery, delivery.id)
        assert sent is not None and sent.status == "sent"
        assert sent.attempts == 1

    with SessionLocal() as db:
        db.execute(delete(NotificationDelivery).where(NotificationDelivery.status == "pending"))
        db.commit()
        user = _new_user(db)
        channel = _new_channel(db, user.id)
        _new_rule(db, user.id, channel.id)
        job = _new_job(db, user.id)
        enqueue_terminal_for_job(db, job)
        failed = db.scalar(
            select(NotificationDelivery).where(NotificationDelivery.job_id == job.id)
        )
        assert failed is not None

    async def fail_send(*args, **kwargs):  # noqa: ANN002, ANN003
        return SendResult(False, 500, "boom")

    monkeypatch.setattr("liberastra.services.notifications.worker.send", fail_send)
    assert asyncio.run(worker._send_once()) is True
    with SessionLocal() as db:
        retried = db.get(NotificationDelivery, failed.id)
        assert retried is not None
        assert retried.status == "pending"
        assert retried.attempts == 1
        assert retried.next_attempt_at is not None

    async def bad_request(*args, **kwargs):  # noqa: ANN002, ANN003
        return SendResult(False, 400, "bad request")

    monkeypatch.setattr("liberastra.services.notifications.worker.send", bad_request)
    with SessionLocal() as db:
        retried = db.get(NotificationDelivery, failed.id)
        assert retried is not None
        retried.next_attempt_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert asyncio.run(worker._send_once()) is True
    with SessionLocal() as db:
        dead = db.get(NotificationDelivery, failed.id)
        assert dead is not None and dead.status == "failed"


def test_progress_tick_dedup_and_quiet(auth_header: dict[str, str]) -> None:
    with SessionLocal() as db:
        user = _new_user(db)
        channel = _new_channel(db, user.id)
        rule = _new_rule(
            db,
            user.id,
            channel.id,
            events=["job.progress"],
            interval=3600,
        )
        rule.template_progress = "running={running} count={count}\n{jobs}"
        db.commit()
        _new_job(db, user.id, kind="video.motion", status="running")
        scheduler = NotificationScheduler()
        assert scheduler.progress_tick(db) == 1
        delivery = db.scalar(
            select(NotificationDelivery).where(
                NotificationDelivery.rule_id == rule.id,
                NotificationDelivery.event == "job.progress",
            )
        )
        assert delivery is not None
        assert "running=1" in delivery.body
        assert "count=1" in delivery.body
        assert scheduler.progress_tick(db) == 0
        rule.quiet_hours = {
            "start": "00:00",
            "end": "23:59",
            "timezone": "UTC",
        }
        db.commit()
        assert scheduler.progress_tick(db) == 0


def test_terminal_sweep_and_cleanup(auth_header: dict[str, str]) -> None:
    with SessionLocal() as db:
        user = _new_user(db)
        channel = _new_channel(db, user.id)
        _new_rule(db, user.id, channel.id)
        job = _new_job(db, user.id)
        scheduler = NotificationScheduler()
        assert scheduler.terminal_sweep(db) >= 1
        assert scheduler.terminal_sweep(db) >= 0
        delivery = db.scalar(
            select(NotificationDelivery).where(NotificationDelivery.job_id == job.id)
        )
        assert delivery is not None
        delivery.status = "sent"
        delivery.created_at = utcnow() - timedelta(days=31)
        db.commit()
        assert scheduler.cleanup(db) >= 1
        assert db.get(NotificationDelivery, delivery.id) is None


def test_canvas_summary_job_lifecycle(auth_header: dict[str, str]) -> None:
    with SessionLocal() as db:
        user = _new_user(db)
        canvas = Canvas(name="汇总画布", graph={}, owner_id=user.id)
        db.add(canvas)
        db.commit()
        db.refresh(canvas)
        run_id = "a" * 32
        _create_run_summary(canvas, user.id, run_id)
        summary = db.get(Job, run_id)
        assert summary is not None
        assert summary.kind == "canvas.run"
        assert summary.status == "running"
        assert summary.params["synthetic"] is True

        channel = _new_channel(db, user.id)
        _new_rule(db, user.id, channel.id, events=["job.failed"])
        plan = {
            "n1": {"node_id": "n1", "status": "succeeded"},
            "n2": {"node_id": "n2", "status": "failed"},
        }
        _finalize_run(db, run_id, canvas, ["n1", "n2"], plan, False)
        db.refresh(summary)
        assert summary.status == "failed"
        assert summary.finished_at is not None
        assert summary.params["success_count"] == 1
        assert summary.params["failed_count"] == 1
        delivery = db.scalar(
            select(NotificationDelivery).where(NotificationDelivery.job_id == run_id)
        )
        assert delivery is not None
        assert "汇总画布" in delivery.title
