"""通知渠道/规则/投递 API 集成测试。"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from liberastra.core.db import SessionLocal
from liberastra.core.security import hash_password
from liberastra.models import Job, User, utcnow
from liberastra.services.notifications.adapters import (
    SendResult,
    TelegramChat,
    TelegramChatsResult,
)


def _channel_payload(name: str = "测试 Telegram") -> dict:
    return {
        "name": name,
        "type": "telegram",
        "config": {
            "bot_token": "123456789:TEST-TOKEN-ABCD",
            "chat_id": "-1001234567890",
            "parse_mode": "HTML",
        },
    }


def test_channel_crud_and_masking(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    created = client.post(
        "/api/v1/notifications/channels", json=_channel_payload(), headers=auth_header
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "测试 Telegram"
    assert body["config"]["bot_token"].startswith("****")
    assert body["config"]["bot_token"].endswith("ABCD")
    assert body["config"]["chat_id"] == "-1001234567890"
    assert "config_encrypted" not in body

    listed = client.get("/api/v1/notifications/channels", headers=auth_header)
    assert listed.status_code == 200
    assert any(item["id"] == body["id"] for item in listed.json())

    updated = client.patch(
        f"/api/v1/notifications/channels/{body['id']}",
        json={"config": {"bot_token": "987654321:NEW-TOKEN-WXYZ"}},
        headers=auth_header,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["config"]["bot_token"].endswith("WXYZ")
    assert updated.json()["config"]["chat_id"] == "-1001234567890"

    duplicate = client.post(
        "/api/v1/notifications/channels", json=_channel_payload(), headers=auth_header
    )
    assert duplicate.status_code == 409

    deleted = client.delete(
        f"/api/v1/notifications/channels/{body['id']}", headers=auth_header
    )
    assert deleted.status_code == 204


def test_channel_validation_and_clear_secret(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    bad_url = client.post(
        "/api/v1/notifications/channels",
        json={
            "name": "坏 Webhook",
            "type": "webhook",
            "config": {"url": "file:///etc/passwd"},
        },
        headers=auth_header,
    )
    assert bad_url.status_code == 400

    per_channel_proxy = client.post(
        "/api/v1/notifications/channels",
        json={
            "name": "带代理",
            "type": "webhook",
            "config": {"url": "https://example.test/hook", "proxy": "http://127.0.0.1:7890"},
        },
        headers=auth_header,
    )
    assert per_channel_proxy.status_code == 400
    assert "全局代理" in per_channel_proxy.json()["detail"]

    created = client.post(
        "/api/v1/notifications/channels",
        json={
            "name": "飞书",
            "type": "feishu",
            "config": {
                "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/abc",
                "secret": "feishu-secret",
                "use_proxy": False,
            },
        },
        headers=auth_header,
    )
    assert created.status_code == 201, created.text
    assert created.json()["config"]["use_proxy"] is False
    channel_id = created.json()["id"]
    cleared = client.patch(
        f"/api/v1/notifications/channels/{channel_id}",
        json={"clear_secret": True},
        headers=auth_header,
    )
    assert cleared.status_code == 200, cleared.text
    assert "secret" not in cleared.json()["config"]


def test_channel_test_send_and_delivery_retry(
    client: TestClient, auth_header: dict[str, str], monkeypatch
) -> None:
    created = client.post(
        "/api/v1/notifications/channels",
        json=_channel_payload("测试发送"),
        headers=auth_header,
    )
    channel_id = created.json()["id"]

    async def ok_send(*args, **kwargs):  # noqa: ANN002, ANN003
        return SendResult(True, 200, "ok")

    monkeypatch.setattr("liberastra.api.routes.notifications.send", ok_send)
    sent = client.post(
        f"/api/v1/notifications/channels/{channel_id}/test", headers=auth_header
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["ok"] is True

    deliveries = client.get(
        "/api/v1/notifications/deliveries", params={"event": "test"}, headers=auth_header
    )
    assert deliveries.status_code == 200
    item = deliveries.json()["items"][0]
    assert item["status"] == "sent"
    assert item["channel_id"] == channel_id

    async def fail_send(*args, **kwargs):  # noqa: ANN002, ANN003
        return SendResult(False, 500, "boom")

    monkeypatch.setattr("liberastra.api.routes.notifications.send", fail_send)
    failed = client.post(
        f"/api/v1/notifications/channels/{channel_id}/test", headers=auth_header
    )
    assert failed.status_code == 200
    assert failed.json()["ok"] is False
    deliveries = client.get(
        "/api/v1/notifications/deliveries", params={"event": "test"}, headers=auth_header
    )
    failed_item = deliveries.json()["items"][0]
    assert failed_item["status"] == "failed"

    retried = client.post(
        f"/api/v1/notifications/deliveries/{failed_item['id']}/retry",
        headers=auth_header,
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "pending"


def test_telegram_chat_lookup(
    client: TestClient, auth_header: dict[str, str], monkeypatch
) -> None:
    created = client.post(
        "/api/v1/notifications/channels",
        json=_channel_payload("获取 Chat ID"),
        headers=auth_header,
    )
    channel_id = created.json()["id"]
    captured: dict = {}

    async def fake_fetch(token: str, **kwargs):  # noqa: ANN003
        captured["token"] = token
        captured.update(kwargs)
        return TelegramChatsResult(
            ok=True,
            chats=[
                TelegramChat(id="100200300", type="private", title="Ada"),
                TelegramChat(id="-100123", type="supergroup", title="Team"),
            ],
        )

    monkeypatch.setattr(
        "liberastra.api.routes.notifications.fetch_telegram_chats", fake_fetch
    )
    saved = client.post(
        "/api/v1/notifications/telegram/chats",
        json={"channel_id": channel_id},
        headers=auth_header,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["items"][0] == {
        "id": "100200300",
        "type": "private",
        "title": "Ada",
    }
    assert captured["token"] == "123456789:TEST-TOKEN-ABCD"
    assert captured["use_proxy"] is True
    assert "TEST-TOKEN" not in saved.text

    typed = client.post(
        "/api/v1/notifications/telegram/chats",
        json={"channel_id": channel_id, "bot_token": "987654321:FORM-TOKEN", "use_proxy": False},
        headers=auth_header,
    )
    assert typed.status_code == 200, typed.text
    assert captured["token"] == "987654321:FORM-TOKEN"
    assert captured["use_proxy"] is False

    invalid = client.post(
        "/api/v1/notifications/telegram/chats",
        json={"bot_token": ":ONLY-SECRET"},
        headers=auth_header,
    )
    assert invalid.status_code == 400
    assert "Bot Token" in invalid.json()["detail"]

    missing = client.post(
        "/api/v1/notifications/telegram/chats", json={}, headers=auth_header
    )
    assert missing.status_code == 400

    async def failed_fetch(token: str, **kwargs):  # noqa: ANN003
        return TelegramChatsResult(ok=False, message="getUpdates failed")

    monkeypatch.setattr(
        "liberastra.api.routes.notifications.fetch_telegram_chats", failed_fetch
    )
    failed = client.post(
        "/api/v1/notifications/telegram/chats",
        json={"channel_id": channel_id},
        headers=auth_header,
    )
    assert failed.status_code == 502
    assert failed.json()["detail"] == "getUpdates failed"

    feishu = client.post(
        "/api/v1/notifications/channels",
        json={
            "name": "飞书不可获取 Chat ID",
            "type": "feishu",
            "config": {"webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/abc"},
        },
        headers=auth_header,
    ).json()
    wrong_type = client.post(
        "/api/v1/notifications/telegram/chats",
        json={"channel_id": feishu["id"]},
        headers=auth_header,
    )
    assert wrong_type.status_code == 400


def test_template_error_is_redacted() -> None:
    from liberastra.services.notifications.service import _apply_template

    job = Job(
        kind="image.generate",
        status="failed",
        progress=0.5,
        error="request failed Authorization: Bearer secret-token",
        outputs=[],
        created_at=utcnow(),
        updated_at=utcnow(),
        finished_at=utcnow(),
    )
    body = _apply_template("{job_name} {status} {error}", "任务", "默认正文", job, None)
    assert "任务" in body
    assert "failed" in body
    assert "secret-token" not in body
    assert "Bearer ***" in body


def test_rule_crud_and_validation(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    channel = client.post(
        "/api/v1/notifications/channels",
        json=_channel_payload("规则渠道"),
        headers=auth_header,
    ).json()
    payload = {
        "name": "默认规则",
        "events": ["job.succeeded", "job.failed"],
        "progress_interval_seconds": 900,
        "channel_ids": [channel["id"]],
    }
    created = client.post(
        "/api/v1/notifications/rules", json=payload, headers=auth_header
    )
    assert created.status_code == 201, created.text
    rule = created.json()
    assert rule["channel_ids"] == [channel["id"]]
    assert rule["events"] == ["job.succeeded", "job.failed"]

    invalid_event = client.post(
        "/api/v1/notifications/rules",
        json={**payload, "name": "坏事件", "events": ["job.nope"]},
        headers=auth_header,
    )
    assert invalid_event.status_code == 422

    invalid_quiet = client.post(
        "/api/v1/notifications/rules",
        json={
            **payload,
            "name": "坏静默",
            "quiet_hours": {"start": "25:00", "end": "08:00", "timezone": "Asia/Shanghai"},
        },
        headers=auth_header,
    )
    assert invalid_quiet.status_code == 400

    updated = client.patch(
        f"/api/v1/notifications/rules/{rule['id']}",
        json={"enabled": False, "job_kinds": ["canvas.run"]},
        headers=auth_header,
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["job_kinds"] == ["canvas.run"]

    deleted = client.delete(
        f"/api/v1/notifications/rules/{rule['id']}", headers=auth_header
    )
    assert deleted.status_code == 204


def test_notification_meta(client: TestClient, auth_header: dict[str, str]) -> None:
    resp = client.get("/api/v1/notifications/meta", headers=auth_header)
    assert resp.status_code == 200
    body = resp.json()
    assert "telegram" in body["channel_types"]
    assert "job.progress" in body["events"]
    assert body["languages"] == ["zh-CN", "en"]


def test_channel_owner_isolation(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    created = client.post(
        "/api/v1/notifications/channels",
        json=_channel_payload("管理员私有"),
        headers=auth_header,
    ).json()

    username = f"user-{uuid4().hex[:8]}"
    password = "user-pass-123"
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == username)) is None:
            db.add(User(username=username, password_hash=hash_password(password)))
            db.commit()
    login = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert login.status_code == 200
    other = {"Authorization": f"Bearer {login.json()['access_token']}"}

    listed = client.get("/api/v1/notifications/channels", headers=other)
    assert listed.status_code == 200
    assert all(item["id"] != created["id"] for item in listed.json())

    forbidden = client.patch(
        f"/api/v1/notifications/channels/{created['id']}",
        json={"name": "偷改"},
        headers=other,
    )
    assert forbidden.status_code == 404


def test_synthetic_canvas_job_hidden_and_not_cancelable(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.username == "admin"))
        assert admin is not None
        job = Job(
            id=uuid4().hex,
            kind="canvas.run",
            status="succeeded",
            progress=1.0,
            owner_id=admin.id,
            params={"synthetic": True, "canvas_id": "c1"},
            finished_at=utcnow(),
        )
        db.add(job)
        db.commit()
        job_id = job.id

    listed = client.get("/api/v1/jobs", headers=auth_header)
    assert listed.status_code == 200
    assert all(item["id"] != job_id for item in listed.json())
    assert all(not (item["params"] or {}).get("synthetic") for item in listed.json())

    canceled = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=auth_header)
    assert canceled.status_code == 409
    retried = client.post(f"/api/v1/jobs/{job_id}/retry", headers=auth_header)
    assert retried.status_code == 409
