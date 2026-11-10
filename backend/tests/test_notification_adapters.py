"""通知适配器与渠道配置的单元测试（MockTransport，无外呼）。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
from unittest.mock import patch

import httpx
import pytest

from liberastra.services.notifications.adapters import (
    NotificationMessage,
    build_request,
    fetch_telegram_chats,
    interpret_response,
    send,
)
from liberastra.services.notifications.config import (
    ConfigError,
    decrypt_config,
    encrypt_config,
    mask_config,
    merge_config,
    validate_config,
)

MSG = NotificationMessage(
    title="标题",
    body="正文",
    event="job.succeeded",
    job_id="job-123",
    link="http://example.test/jobs/job-123",
    delivery_id=7,
)


def test_config_roundtrip_and_mask() -> None:
    config = validate_config(
        "telegram",
        {"bot_token": "123456:ABCDEFGH", "chat_id": -1001, "parse_mode": "HTML"},
    )
    encrypted = encrypt_config(config)
    assert "ABCDEFGH" not in encrypted
    assert decrypt_config(encrypted)["chat_id"] == "-1001"
    assert config["use_proxy"] is True
    masked = mask_config("telegram", config)
    assert masked["bot_token"].endswith("EFGH")
    assert masked["chat_id"] == "-1001"
    direct = validate_config(
        "webhook", {"url": "https://example.test/hook", "use_proxy": False}
    )
    assert direct["use_proxy"] is False
    assert mask_config("webhook", direct)["use_proxy"] is False
    bark = validate_config(
        "bark",
        {"server_url": "https://bark.example.test", "device_key": "device-key"},
    )
    assert mask_config("bark", bark)["server_url"] == "https://bark.example.test"
    assert mask_config("bark", bark)["device_key"].startswith("****")


def test_config_validation() -> None:
    with pytest.raises(ConfigError):
        validate_config("webhook", {"url": "file:///etc/passwd"})
    with pytest.raises(ConfigError):
        validate_config(
            "webhook", {"url": "https://user:pass@example.test/hook"}
        )
    with pytest.raises(ConfigError):
        validate_config(
            "webhook", {"url": "https://example.test/hook", "proxy": "http://p:1"}
        )
    with pytest.raises(ConfigError):
        validate_config("telegram", {"bot_token": "x", "chat_id": ""})
    with pytest.raises(ConfigError):
        validate_config(
            "telegram",
            {"bot_token": ":FAKE-SECRET-FOR-VALIDATION", "chat_id": "1"},
        )
    with pytest.raises(ConfigError):
        validate_config(
            "telegram",
            {"bot_token": "123456:ABCDEFGH", "chat_id": "123456"},
        )
    merged = merge_config(
        "feishu",
        {"webhook_url": "https://example.test/hook", "secret": "old-secret"},
        {},
        clear_secret=True,
    )
    assert "secret" not in merged


def test_telegram_request_and_business_error() -> None:
    request = build_request(
        "telegram",
        {"bot_token": "t", "chat_id": "-1", "parse_mode": "HTML", "disable_preview": True},
        MSG,
    )
    assert request["url"].endswith("/bott/sendMessage")
    assert request["json"]["chat_id"] == "-1"
    assert MSG.link in request["json"]["text"]
    assert interpret_response("telegram", 200, '{"ok":true}').ok is True
    failed = interpret_response("telegram", 200, '{"ok":false,"description":"bad"}')
    assert failed.ok is False
    assert "bad" in failed.message


def test_feishu_signature() -> None:
    with patch("liberastra.services.notifications.adapters.time.time", return_value=1700000000):
        request = build_request(
            "feishu",
            {"webhook_url": "https://open.feishu.cn/hook", "secret": "s3cret"},
            MSG,
        )
    expected = base64.b64encode(
        hmac.new(b"s3cret", b"1700000000\ns3cret", hashlib.sha256).digest()
    ).decode()
    assert request["json"]["timestamp"] == "1700000000"
    assert request["json"]["sign"] == expected
    assert interpret_response("feishu", 200, '{"code":0}').ok is True
    assert interpret_response("feishu", 200, '{"code":19001,"msg":"bad"}').ok is False


def test_dingtalk_signature_and_request() -> None:
    with patch(
        "liberastra.services.notifications.adapters.time.time", return_value=1700000000.123
    ):
        request = build_request(
            "dingtalk",
            {
                "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=x",
                "secret": "s3cret",
                "at_mobiles": ["13800000000"],
                "at_all": False,
            },
            MSG,
        )
    assert "timestamp=1700000000123" in request["url"]
    assert "sign=" in request["url"]
    assert request["json"]["msgtype"] == "markdown"
    assert request["json"]["at"]["atMobiles"] == ["13800000000"]
    assert interpret_response("dingtalk", 200, '{"errcode":0}').ok is True
    assert interpret_response("dingtalk", 200, '{"errcode":310000}').ok is False


def test_bark_request_and_business_error() -> None:
    request = build_request(
        "bark",
        {"server_url": "https://api.day.app/", "device_key": "dev", "group": "g", "sound": "s"},
        MSG,
    )
    assert request["url"] == "https://api.day.app/dev"
    assert request["json"]["title"] == "标题"
    assert request["json"]["url"] == MSG.link
    push = build_request(
        "bark",
        {"server_url": "https://api.day.app/push", "device_key": "dev"},
        MSG,
    )
    assert push["url"] == "https://api.day.app/push"
    assert push["json"]["device_key"] == "dev"
    assert interpret_response("bark", 200, '{"code":200}').ok is True
    assert interpret_response("bark", 200, '{"code":400,"message":"bad"}').ok is False


def test_webhook_hmac_and_template() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = dict(request.headers)
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True})

    template = '{"text":"{title}: {body}","event":"{event}","link":"{link}"}'
    config = {
        "url": "https://example.test/hook",
        "method": "POST",
        "headers": {"X-Test": "1"},
        "hmac_secret": "whsec",
        "body_template": template,
    }
    request = build_request("webhook", config, MSG)
    assert request["json"]["text"] == "标题: 正文"

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await send("webhook", config, MSG, client=client)
            assert result.ok is True

    asyncio.run(run())
    headers = seen["headers"]
    raw = seen["body"]
    assert headers["x-test"] == "1"
    expected = hmac.new(b"whsec", raw, hashlib.sha256).hexdigest()
    assert headers["x-liberastra-signature"] == f"sha256={expected}"
    assert headers["x-liberastra-delivery"] == "7"
    assert json.loads(raw)["event"] == "job.succeeded"


def test_http_error_returns_send_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await send(
                "webhook", {"url": "https://example.test/hook"}, MSG, client=client
            )
            assert result.ok is False
            assert result.status == 403
            assert "403" in result.message

    asyncio.run(run())


def test_telegram_fetch_chats_parses_updates() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": [
                    {
                        "update_id": 1,
                        "message": {
                            "chat": {"id": -1001, "type": "supergroup", "title": "Team"}
                        },
                    },
                    {
                        "update_id": 2,
                        "message": {
                            "chat": {
                                "id": 576,
                                "type": "private",
                                "first_name": "Ada",
                                "last_name": "Lovelace",
                            }
                        },
                    },
                    {
                        "update_id": 3,
                        "channel_post": {
                            "chat": {"id": -1002, "type": "channel", "title": "News"}
                        },
                    },
                    {
                        "update_id": 4,
                        "message": {
                            "chat": {
                                "id": 576,
                                "type": "private",
                                "first_name": "Ada",
                                "last_name": "Lovelace",
                            }
                        },
                    },
                    {"update_id": 5, "message": {"chat": {"id": -1003, "type": "group"}}},
                    {
                        "update_id": 6,
                        "my_chat_member": {
                            "chat": {"id": -1004, "type": "group", "title": "Ignored"}
                        },
                    },
                ],
            },
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await fetch_telegram_chats("123456:SECRET", client=client)
        assert result.ok is True, result.message
        assert [chat.id for chat in result.chats] == ["-1003", "576", "-1002", "-1001"]
        assert result.chats[0].title == ""
        assert result.chats[1].title == "Ada Lovelace"
        assert result.chats[2].type == "channel"
        assert seen[0].split("?")[0].endswith("/getUpdates")
        assert "SECRET" not in str(result.chats)

    asyncio.run(run())


def test_telegram_fetch_chats_errors_are_safe() -> None:
    async def invalid() -> None:
        result = await fetch_telegram_chats(":SECRET")
        assert result.ok is False
        assert "Bot Token" in result.message

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot connect to {request.url}", request=request)

    async def network_error() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await fetch_telegram_chats("123456:SECRET", client=client)
        assert result.ok is False
        assert "SECRET" not in result.message
        assert "***" in result.message

    def conflict(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "ok": False,
                "description": "Conflict: can't use getUpdates method while webhook is active",
            },
        )

    async def webhook_conflict() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(conflict)) as client:
            result = await fetch_telegram_chats("123456:SECRET", client=client)
        assert result.ok is False
        assert "webhook" in result.message

    asyncio.run(invalid())
    asyncio.run(network_error())
    asyncio.run(webhook_conflict())
