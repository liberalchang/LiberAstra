"""鉴权路由：初始化向导、登录、当前用户。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.core.security import create_access_token, hash_password, verify_password
from liberastra.models import User
from liberastra.schemas.auth import AuthStatus, LoginRequest, SetupRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status", response_model=AuthStatus)
def auth_status(db: DbSession) -> AuthStatus:
    has_user = db.scalar(select(func.count()).select_from(User)) > 0
    return AuthStatus(initialized=has_user)


@router.post("/setup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def setup(body: SetupRequest, db: DbSession) -> User:
    """首次启动初始化：创建唯一的管理员账号。"""
    has_user = db.scalar(select(func.count()).select_from(User)) > 0
    if has_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已完成初始化")
    user = User(username=body.username, password_hash=hash_password(body.password), is_admin=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return TokenResponse(access_token=create_access_token(user.username))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
