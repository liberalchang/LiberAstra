"""安全工具：argon2 密码哈希、JWT 会话、API Token（只存 SHA-256 哈希）、Fernet 密钥派生。"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet

from liberastra.core.config import get_settings

API_TOKEN_PREFIX = "astra_"

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


def create_access_token(subject: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.resolved_secret_key, algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    """返回 subject（用户名），无效或过期返回 None。"""
    try:
        payload = jwt.decode(
            token, get_settings().resolved_secret_key, algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None


def generate_api_token() -> tuple[str, str, str]:
    """生成 API Token，返回 (明文, sha256 哈希, 展示前缀)。明文只在创建时返回一次。"""
    token = API_TOKEN_PREFIX + secrets.token_urlsafe(32)
    return token, hash_api_token(token), token[:16]


def hash_api_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_fernet() -> Fernet:
    """由主密钥派生 Fernet 密钥，用于 Provider 密钥等敏感配置的加密存储。"""
    digest = hashlib.sha256(get_settings().resolved_secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))
