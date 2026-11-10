"""五类通知渠道的 HTTP 适配器。

纯函数负责构造请求和解析响应，`send()` 负责真实发送；测试可用
`httpx.MockTransport` 注入 client。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_plus

import httpx

from liberastra.services.notifications.config import (
    ConfigError,
    validate_telegram_token,
)

_PLACEHOLDER = re.compile(r"\{(title|body|event|job_id|link|delivery_id)\}")


@dataclass
class NotificationMessage:
    title: str
    body: str
    event: str = "test"
    job_id: str | None = None
    link: str | None = None
    delivery_id: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class SendResult:
    ok: bool
    status: int | None = None
    message: str = ""
    retry_after: float | None = None


@dataclass
class TelegramChat:
    id: str
    type: str
    title: str


@dataclass
class TelegramChatsResult:
    ok: bool
    chats: list[TelegramChat] = field(default_factory=list)
    message: str = ""


def _short(text: str, limit: int = 300) -> str:
    text = " ".join(str(text).split())
    return text[:limit]


def _json_or_none(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _escape_telegram(text: str, parse_mode: str) -> str:
    if parse_mode == "MarkdownV2":
        return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _telegram_request(config: dict[str, Any], message: NotificationMessage) -> dict[str, Any]:
    token = str(config.get("bot_token") or "")
    if not token:
        raise ConfigError("Telegram bot_token 缺失")
    parse_mode = str(config.get("parse_mode") or "HTML")
    text = f"{message.title}\n{message.body}"
    if message.link:
        text = f"{text}\n{message.link}"
    text = _escape_telegram(text, parse_mode)[:4096]
    return {
        "method": "POST",
        "url": f"https://api.telegram.org/bot{token}/sendMessage",
        "json": {
            "chat_id": str(config.get("chat_id") or ""),
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": bool(config.get("disable_preview", True)),
        },
        "headers": {},
    }


_TELEGRAM_CHAT_TYPES = {"private", "group", "supergroup", "channel"}


def _telegram_chat_title(chat: dict[str, Any]) -> str:
    title = str(chat.get("title") or "").strip()
    if title:
        return _short(title, 80)
    name = " ".join(
        str(part).strip()
        for part in (chat.get("first_name"), chat.get("last_name"))
        if part is not None and str(part).strip()
    )
    if name:
        return _short(name, 80)
    return _short(str(chat.get("username") or ""), 80)


def parse_telegram_chats(payload: dict[str, Any]) -> list[TelegramChat]:
    updates = payload.get("result")
    if not isinstance(updates, list):
        return []
    chats: dict[str, TelegramChat] = {}
    for update in reversed(updates):
        if not isinstance(update, dict):
            continue
        message = None
        for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
            candidate = update.get(key)
            if isinstance(candidate, dict):
                message = candidate
                break
        if message is None:
            continue
        chat = message.get("chat")
        if not isinstance(chat, dict):
            continue
        chat_id = chat.get("id")
        chat_type = str(chat.get("type") or "")
        if chat_id is None or chat_type not in _TELEGRAM_CHAT_TYPES:
            continue
        key = str(chat_id)
        if key in chats:
            continue
        chats[key] = TelegramChat(
            id=key,
            type=chat_type,
            title=_telegram_chat_title(chat),
        )
    return list(chats.values())


def _feishu_sign(secret: str, timestamp: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}\n{secret}".encode(),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def _feishu_request(config: dict[str, Any], message: NotificationMessage) -> dict[str, Any]:
    url = str(config.get("webhook_url") or "")
    body: dict[str, Any] = {
        "msg_type": "text",
        "content": {"text": f"{message.title}\n{message.body}"[:30000]},
    }
    secret = str(config.get("secret") or "")
    if secret:
        timestamp = str(int(time.time()))
        body["timestamp"] = timestamp
        body["sign"] = _feishu_sign(secret, timestamp)
    return {"method": "POST", "url": url, "json": body, "headers": {}}


def _dingtalk_sign(secret: str, timestamp: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}\n{secret}".encode(),
        hashlib.sha256,
    ).digest()
    return quote_plus(base64.b64encode(digest).decode("utf-8"))


def _dingtalk_request(config: dict[str, Any], message: NotificationMessage) -> dict[str, Any]:
    url = str(config.get("webhook_url") or "")
    secret = str(config.get("secret") or "")
    if secret:
        timestamp = str(round(time.time() * 1000))
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}timestamp={timestamp}&sign={_dingtalk_sign(secret, timestamp)}"
    body: dict[str, Any] = {
        "msgtype": "markdown",
        "markdown": {
            "title": message.title[:100],
            "text": message.body[:20000],
        },
        "at": {
            "atMobiles": list(config.get("at_mobiles") or []),
            "isAtAll": bool(config.get("at_all", False)),
        },
    }
    return {"method": "POST", "url": url, "json": body, "headers": {}}


def _bark_request(config: dict[str, Any], message: NotificationMessage) -> dict[str, Any]:
    server = str(config.get("server_url") or "https://api.day.app").rstrip("/")
    device = str(config.get("device_key") or "")
    body: dict[str, Any] = {
        "title": message.title[:256],
        "body": message.body[:1024],
    }
    if config.get("group"):
        body["group"] = str(config["group"])
    if config.get("sound"):
        body["sound"] = str(config["sound"])
    if message.link:
        body["url"] = message.link
    if server.endswith("/push"):
        # Bark 的 /push 接口把 device_key 放在 JSON body 里。
        body["device_key"] = device
        url = server
    else:
        url = f"{server}/{device}"
    return {
        "method": "POST",
        "url": url,
        "json": body,
        "headers": {},
    }


def _render_webhook_template(template: str, message: NotificationMessage) -> str:
    values = {
        "title": message.title,
        "body": message.body,
        "event": message.event,
        "job_id": message.job_id or "",
        "link": message.link or "",
        "delivery_id": str(message.delivery_id or ""),
    }
    return _PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), template)


def _webhook_payload(message: NotificationMessage) -> dict[str, Any]:
    return {
        "event": message.event,
        "title": message.title,
        "body": message.body,
        "job": {"id": message.job_id} if message.job_id else None,
        "link": message.link,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _webhook_request(config: dict[str, Any], message: NotificationMessage) -> dict[str, Any]:
    url = str(config.get("url") or "")
    headers = {
        str(k): str(v)
        for k, v in (config.get("headers") or {}).items()
        if str(k).lower()
        not in {"host", "content-length", "transfer-encoding", "connection"}
    }
    template = config.get("body_template")
    if template:
        rendered = _render_webhook_template(str(template), message)
        try:
            body = json.loads(rendered)
        except ValueError as exc:
            raise ConfigError("body_template 渲染后不是合法 JSON") from exc
        if not isinstance(body, dict):
            raise ConfigError("body_template 渲染后必须是 JSON 对象")
    else:
        body = _webhook_payload(message)
    headers = {**headers, "Content-Type": "application/json"}
    secret = str(config.get("hmac_secret") or "")
    if secret:
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        headers["X-LiberAstra-Signature"] = f"sha256={signature}"
        headers["X-LiberAstra-Timestamp"] = str(int(time.time()))
        headers["X-LiberAstra-Delivery"] = str(message.delivery_id or "")
    return {"method": "POST", "url": url, "json": body, "headers": headers}


_BUILDERS = {
    "telegram": _telegram_request,
    "feishu": _feishu_request,
    "dingtalk": _dingtalk_request,
    "bark": _bark_request,
    "webhook": _webhook_request,
}


def build_request(channel_type: str, config: dict[str, Any], message: NotificationMessage) -> dict[str, Any]:
    builder = _BUILDERS.get(channel_type)
    if builder is None:
        raise ConfigError(f"未知渠道类型: {channel_type}")
    return builder(config, message)


def interpret_response(channel_type: str, status: int, text: str) -> SendResult:
    body = _json_or_none(text)
    if status < 200 or status >= 300:
        return SendResult(False, status, _short(f"HTTP {status}: {text}"))
    if channel_type == "telegram":
        if body is not None and body.get("ok") is True:
            return SendResult(True, status, "ok")
        return SendResult(False, status, _short((body or {}).get("description") or text))
    if channel_type == "feishu":
        code = body.get("code", body.get("StatusCode", 0)) if body else 0
        if code in (0, None):
            return SendResult(True, status, "ok")
        return SendResult(False, status, _short((body or {}).get("msg") or text))
    if channel_type == "dingtalk":
        if body is not None and body.get("errcode") == 0:
            return SendResult(True, status, "ok")
        return SendResult(False, status, _short((body or {}).get("errmsg") or text))
    if channel_type == "bark":
        code = body.get("code") if body else None
        if code in (0, 200, None):
            return SendResult(True, status, "ok")
        return SendResult(False, status, _short((body or {}).get("message") or text))
    return SendResult(True, status, "ok")


async def send(
    channel_type: str,
    config: dict[str, Any],
    message: NotificationMessage,
    *,
    timeout: float = 10.0,
    proxy: str | None = None,
    use_proxy: bool = True,
    client: httpx.AsyncClient | None = None,
) -> SendResult:
    try:
        request = build_request(channel_type, config, message)
    except ConfigError as exc:
        return SendResult(False, None, str(exc))
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=timeout,
            proxy=proxy or None,
            trust_env=use_proxy,
            follow_redirects=False,
        )
    try:
        response = await client.request(
            request["method"],
            request["url"],
            json=request.get("json"),
            headers=request.get("headers") or {},
        )
        result = interpret_response(channel_type, response.status_code, response.text)
        if response.status_code == 429:
            header = response.headers.get("Retry-After")
            if header:
                try:
                    result.retry_after = max(0.0, float(header))
                except ValueError:
                    pass
            if result.retry_after is None:
                body = _json_or_none(response.text)
                params = body.get("parameters") if body else None
                if isinstance(params, dict) and params.get("retry_after") is not None:
                    try:
                        result.retry_after = max(0.0, float(params["retry_after"]))
                    except (TypeError, ValueError):
                        pass
        return result
    except httpx.HTTPError as exc:
        return SendResult(False, None, _short(f"{type(exc).__name__}: {exc}"))
    finally:
        if owns_client:
            await client.aclose()


async def fetch_telegram_chats(
    bot_token: str,
    *,
    timeout: float = 10.0,
    proxy: str | None = None,
    use_proxy: bool = True,
    client: httpx.AsyncClient | None = None,
) -> TelegramChatsResult:
    try:
        token = validate_telegram_token(bot_token)
    except ConfigError as exc:
        return TelegramChatsResult(ok=False, message=str(exc))
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=timeout,
            proxy=proxy or None,
            trust_env=use_proxy,
            follow_redirects=False,
        )
    try:
        response = await client.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"limit": 100},
        )
        body = _json_or_none(response.text)
        description = str((body or {}).get("description") or "")
        if response.status_code < 200 or response.status_code >= 300:
            message = _short(
                f"HTTP {response.status_code}: {description or response.text}"
            ).replace(token, "***")
            return TelegramChatsResult(ok=False, message=message)
        if body is None or body.get("ok") is not True:
            message = _short(description or "getUpdates 返回异常").replace(token, "***")
            return TelegramChatsResult(ok=False, message=message)
        return TelegramChatsResult(ok=True, chats=parse_telegram_chats(body))
    except httpx.HTTPError as exc:
        message = _short(f"{type(exc).__name__}: {exc}").replace(token, "***")
        return TelegramChatsResult(ok=False, message=message)
    finally:
        if owns_client:
            await client.aclose()
