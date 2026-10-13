"""FastAPI 依赖：Bearer JWT 或 astra_ 开头的 API Token 二选一认证。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from liberastra.core.db import get_db
from liberastra.core.security import API_TOKEN_PREFIX, decode_access_token, hash_api_token
from liberastra.models import ApiToken, User

_bearer = HTTPBearer(auto_error=False)

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="无效或过期的凭据",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None:
        raise _credentials_exc
    token = credentials.credentials

    if token.startswith(API_TOKEN_PREFIX):
        return _user_from_api_token(token, db)

    username = decode_access_token(token)
    if username is None:
        raise _credentials_exc
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise _credentials_exc
    return user


def _as_utc(value: datetime) -> datetime:
    """SQLite 读出的时间戳不带时区，统一按 UTC 处理。"""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _user_from_api_token(token: str, db: Session) -> User:
    record = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_api_token(token)))
    if record is None or record.revoked:
        raise _credentials_exc
    if record.expires_at is not None and _as_utc(record.expires_at) < datetime.now(UTC):
        raise _credentials_exc
    record.last_used_at = datetime.now(UTC)
    db.commit()
    return record.owner


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
