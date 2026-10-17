"""系统路由：信息、备份导出、手动触发清理、运行时偏好。"""

from __future__ import annotations

import tempfile
import zipfile

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from liberastra import __version__
from liberastra.api.deps import CurrentUser, DbSession, require_admin
from liberastra.core.config import get_settings
from liberastra.core.db import SessionLocal
from liberastra.models import Asset, Job, Provider, User
from liberastra.services.maintenance import cleanup_old_data
from liberastra.services.preferences import all_prefs, set_pref

router = APIRouter(prefix="/system", tags=["system"])


class PreferencesUpdate(BaseModel):
    """运行时偏好。None 表示该项保持不变。"""

    comfy_wait_timeout_seconds: int | None = Field(default=None, ge=60, le=14400)
    api_wait_timeout_seconds: int | None = Field(default=None, ge=30, le=3600)
    llm_request_timeout_seconds: int | None = Field(default=None, ge=30, le=3600)
    # 0=并行（默认），1=同一台主机上的 Provider 任务互斥串行
    serial_same_host: int | None = Field(default=None, ge=0, le=1)


@router.get("/preferences")
def get_preferences(user: CurrentUser, db: DbSession) -> dict[str, int]:
    """读取运行时偏好：ComfyUI 等待超时、同步接口等待超时等。"""
    return all_prefs(db)


@router.patch("/preferences")
def update_preferences(body: PreferencesUpdate, user: CurrentUser, db: DbSession) -> dict[str, int]:
    """更新运行时偏好，下一个任务起生效。"""
    for key, value in body.model_dump(exclude_none=True).items():
        set_pref(db, key, value)
    return all_prefs(db)


@router.get("/info")
def system_info(user: CurrentUser, db: DbSession) -> dict:
    settings = get_settings()
    return {
        "version": __version__,
        "data_dir": str(settings.data_dir.resolve()),
        "database": "sqlite" if settings.resolved_database_url.startswith("sqlite") else "postgres",
        "cleanup_retention_days": settings.cleanup_retention_days,
        "counts": {
            "providers": db.scalar(select(func.count()).select_from(Provider)),
            "jobs": db.scalar(select(func.count()).select_from(Job)),
            "assets": db.scalar(select(func.count()).select_from(Asset)),
            "users": db.scalar(select(func.count()).select_from(User)),
        },
    }


@router.post("/cleanup")
def cleanup(db: DbSession, user: User = Depends(require_admin)) -> dict:  # noqa: B008
    """手动触发清理（按 cleanup_retention_days；为 0 时不动作）。"""
    days = get_settings().cleanup_retention_days
    if days <= 0:
        return {"jobs": 0, "assets": 0, "note": "清理策略未启用（cleanup_retention_days=0）"}
    return cleanup_old_data(db, days)


@router.get("/backup")
def backup(user: User = Depends(require_admin)) -> FileResponse:  # noqa: B008
    """导出数据目录为 zip（数据库 + 配置 + 产物，不含日志）。"""
    data_dir = get_settings().data_dir.resolve()
    tmp = tempfile.NamedTemporaryFile(prefix="liberastra-backup-", suffix=".zip", delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in data_dir.rglob("*"):
            if not path.is_file() or "logs" in path.parts:
                continue
            zf.write(path, path.relative_to(data_dir))
    return FileResponse(
        tmp.name,
        media_type="application/zip",
        filename=f"liberastra-backup-{_today()}.zip",
    )


def _today() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d")


def run_startup_cleanup() -> None:
    """应用启动时按配置执行一次清理。"""
    days = get_settings().cleanup_retention_days
    if days <= 0:
        return
    db = SessionLocal()
    try:
        cleanup_old_data(db, days)
    finally:
        db.close()
