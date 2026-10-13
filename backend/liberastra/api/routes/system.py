"""系统路由：信息、备份导出、手动触发清理。"""

from __future__ import annotations

import tempfile
import zipfile

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from liberastra import __version__
from liberastra.api.deps import CurrentUser, DbSession, require_admin
from liberastra.core.config import get_settings
from liberastra.core.db import SessionLocal
from liberastra.models import Asset, Job, Provider, User
from liberastra.services.maintenance import cleanup_old_data

router = APIRouter(prefix="/system", tags=["system"])


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
