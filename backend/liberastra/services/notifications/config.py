"""通知渠道配置：Fernet 加密、类型校验、API 掩码。"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit

from liberastra.core.security import get_fernet


class ConfigError(ValueError):
    """渠道配置不合法或无法解密。"""


ALLOWED_FIELDS: dict[str, set[str]] = {
    "telegram": {"bot_token", "chat_id", "parse_mode", "disable_preview"},
    "feishu": {"webhook_url", "secret"},
    "dingtalk": {"webhook_url", "secret", "at_mobiles", "at_all"},
    "bark": {"server_url", "device_key", "group", "sound"},
    "webhook": {"url", "method", "headers", "hmac_secret", "body_template"},
}

SECRET_FIELDS: dict[str, set[str]] = {
    "telegram": {"bot_token"},
    "feishu": {"secret"},
    "dingtalk": {"secret"},
    "bark": {"device_key"},
    "webhook": {"hmac_secret"},
}

URL_FIELDS: dict[str, set[str]] = {
    "telegram": set(),
    "feishu": {"webhook_url"},
    "dingtalk": {"webhook_url"},
    "bark": {"server_url"},
    "webhook": {"url"},
}

REQUIRED_FIELDS: dict[str, set[str]] = {
    "telegram": {"bot_token", "chat_id"},
    "feishu": {"webhook_url"},
    "dingtalk": {"webhook_url"},
    "bark": {"device_key"},
    "webhook": {"url"},
}

DEFAULTS: dict[str, dict[str, Any]] = {
    "telegram": {"parse_mode": "HTML", "disable_preview": True},
    "feishu": {},
    "dingtalk": {"at_mobiles": [], "at_all": False},
    "bark": {"server_url": "https://api.day.app"},
    "webhook": {"method": "POST", "headers": {}},
}

COMMON_FIELDS = {"use_proxy"}
_TELEGRAM_TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]+$")


def _as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("false", "0", "no", "off", "")
    return bool(value)


def encrypt_config(config: dict[str, Any]) -> str:
    raw = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return get_fernet().encrypt(raw).decode("utf-8")


def decrypt_config(encrypted: str) -> dict[str, Any]:
    try:
        raw = get_fernet().decrypt(encrypted.encode("utf-8"))
        value = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        raise ConfigError("渠道配置无法解密，请重新填写") from exc
    if not isinstance(value, dict):
        raise ConfigError("渠道配置格式不正确")
    return value


def _mask_value(value: str) -> str:
    if not value:
        return ""
    return "****" + value[-4:] if len(value) > 4 else "****"


def _mask_url(value: str) -> str:
    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return "****"
    tail = "/***" if parts.path or parts.query or parts.fragment else ""
    return f"{parts.scheme}://{parts.netloc}{tail}"


def mask_config(channel_type: str, config: dict[str, Any]) -> dict[str, Any]:
    """返回可安全给前端的配置：只保留 host / 密钥尾 4 位。"""
    out: dict[str, Any] = {}
    for key, value in config.items():
        if channel_type == "bark" and key == "server_url" and isinstance(value, str):
            out[key] = value
        elif key in URL_FIELDS.get(channel_type, set()) and isinstance(value, str):
            out[key] = _mask_url(value)
        elif key in SECRET_FIELDS.get(channel_type, set()) and isinstance(value, str):
            out[key] = _mask_value(value)
        elif key == "headers" and isinstance(value, dict):
            out[key] = {str(k): "****" for k in value}
        else:
            out[key] = value
    return out


def _validate_url(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field} 不能为空")
    text = value.strip()
    parts = urlsplit(text)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ConfigError(f"{field} 只支持 http/https URL")
    if parts.username or parts.password:
        raise ConfigError(f"{field} 不允许包含用户名密码")
    return text


def _normalize(channel_type: str, config: dict[str, Any]) -> dict[str, Any]:
    allowed = ALLOWED_FIELDS[channel_type] | COMMON_FIELDS
    unknown = sorted(set(config) - allowed)
    if unknown:
        if {"proxy", "verify_tls"} & set(unknown):
            raise ConfigError("第一版只支持全局代理，不提供每渠道 proxy/verify_tls")
        raise ConfigError(f"未知渠道配置字段: {unknown}")

    data = {**DEFAULTS.get(channel_type, {}), **config}
    for field in SECRET_FIELDS.get(channel_type, set()):
        value = data.get(field)
        if isinstance(value, str):
            value = value.strip()
            if value:
                data[field] = value
            else:
                data.pop(field, None)
    if channel_type == "telegram":
        token = validate_telegram_token(data["bot_token"]) if data.get("bot_token") else ""
        bot_id = token.split(":", 1)[0] if token else ""
        if bot_id and str(data.get("chat_id") or "") == bot_id:
            raise ConfigError(
                "Chat ID 不能填 bot 自己的 ID；请填你的用户 ID，或群/频道的负数 ID"
            )

    for field in REQUIRED_FIELDS[channel_type]:
        value = data.get(field)
        if field == "chat_id":
            if value is None or str(value).strip() == "":
                raise ConfigError("chat_id 不能为空")
            data[field] = str(value).strip()
        elif not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{field} 不能为空")

    for field in URL_FIELDS[channel_type]:
        if field in data:
            data[field] = _validate_url(field, data[field])

    if channel_type == "telegram":
        if data.get("parse_mode") not in ("HTML", "MarkdownV2"):
            raise ConfigError("parse_mode 只支持 HTML / MarkdownV2")
        data["disable_preview"] = bool(data.get("disable_preview", True))
    elif channel_type == "dingtalk":
        mobiles = data.get("at_mobiles") or []
        if not isinstance(mobiles, list) or any(not isinstance(m, str) for m in mobiles):
            raise ConfigError("at_mobiles 必须是字符串数组")
        data["at_mobiles"] = [m.strip() for m in mobiles if m.strip()]
        data["at_all"] = bool(data.get("at_all", False))
    elif channel_type == "webhook":
        if data.get("method", "POST").upper() != "POST":
            raise ConfigError("第一版 Webhook 只支持 POST")
        data["method"] = "POST"
        headers = data.get("headers") or {}
        if not isinstance(headers, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in headers.items()
        ):
            raise ConfigError("headers 必须是字符串键值对象")
        data["headers"] = headers
        template = data.get("body_template")
        if template is not None and not isinstance(template, str):
            raise ConfigError("body_template 必须是字符串")
    data["use_proxy"] = _as_bool(data.get("use_proxy"), True)
    return data


def validate_telegram_token(value: Any) -> str:
    token = str(value or "").strip()
    if not token:
        raise ConfigError("bot_token 不能为空")
    if not _TELEGRAM_TOKEN_RE.match(token):
        raise ConfigError(
            "Bot Token 格式不正确：应为「数字 bot ID + 冒号 + 密钥」，"
            "冒号在中间；不要在开头加冒号，也不要只粘贴冒号后的密钥"
        )
    return token


def validate_config(channel_type: str, config: dict[str, Any]) -> dict[str, Any]:
    if channel_type not in ALLOWED_FIELDS:
        raise ConfigError(f"未知渠道类型: {channel_type}")
    if not isinstance(config, dict):
        raise ConfigError("config 必须是对象")
    return _normalize(channel_type, config)


def merge_config(
    channel_type: str,
    existing: dict[str, Any],
    patch: dict[str, Any],
    *,
    clear_secret: bool = False,
) -> dict[str, Any]:
    """合并更新：敏感字段留空=不修改；clear_secret 清空可选密钥。"""
    merged = dict(existing)
    if clear_secret:
        for field in SECRET_FIELDS.get(channel_type, set()):
            merged.pop(field, None)
    for key, value in patch.items():
        if key in SECRET_FIELDS.get(channel_type, set()) and value in (None, ""):
            continue
        merged[key] = value
    return validate_config(channel_type, merged)
