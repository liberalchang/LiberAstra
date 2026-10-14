"""资产库路由：列表、详情、内容下载、删除。"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.models import Asset, User
from liberastra.schemas.asset import AssetOut
from liberastra.storage import resolve

router = APIRouter(prefix="/assets", tags=["assets"])


def _get_owned(db, asset_id: int, user: User) -> Asset:  # noqa: ANN001
    record = db.get(Asset, asset_id)
    if record is None or record.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资产不存在")
    return record


def _download_name(record: Asset) -> str:
    """下载文件名：日期 + 提示词/文案摘要；无摘要时退回落盘文件名。"""
    base = Path(record.path).name
    meta = record.meta or {}
    summary = meta.get("prompt") or meta.get("text") or meta.get("title")
    if not summary:
        return base
    slug = re.sub(r'[\\/:*?"<>|\s]+', "_", str(summary)).strip("_")[:24]
    if not slug:
        return base
    date = record.created_at.strftime("%Y%m%d")
    return f"{date}_{slug}{Path(record.path).suffix}"


@router.get("", response_model=list[AssetOut])
def list_assets(
    user: CurrentUser, db: DbSession, kind: str | None = None, limit: int = 50
) -> list[Asset]:
    stmt = select(Asset).where(Asset.owner_id == user.id).order_by(Asset.created_at.desc())
    if kind:
        kinds = [k.strip() for k in kind.split(",") if k.strip()]
        stmt = stmt.where(Asset.kind.in_(kinds))
    return list(db.scalars(stmt.limit(min(limit, 200))).all())


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: int, user: CurrentUser, db: DbSession) -> Asset:
    return _get_owned(db, asset_id, user)


@router.get("/{asset_id}/content")
def asset_content(asset_id: int, user: CurrentUser, db: DbSession) -> FileResponse:
    record = _get_owned(db, asset_id, user)
    try:
        path = resolve(record.path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法路径") from exc
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件已丢失")
    return FileResponse(path, media_type=record.mime, filename=_download_name(record))


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int, user: CurrentUser, db: DbSession) -> None:
    record = _get_owned(db, asset_id, user)
    try:
        resolve(record.path).unlink(missing_ok=True)
    except ValueError:
        pass
    db.delete(record)
    db.commit()
