"""资产库路由：列表、详情、内容下载、删除。"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from starlette.background import BackgroundTask

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.core.security import create_download_token, decode_download_token
from liberastra.media.thumbs import (
    asset_thumb_path,
    extract_video_thumb,
    image_thumb_bytes,
    remove_asset_thumb,
    store_asset_thumb,
)
from liberastra.models import Asset, Job, User
from liberastra.models.job import TERMINAL_STATUSES
from liberastra.providers.base import ProviderError
from liberastra.schemas.asset import (
    AssetJobDeleteOut,
    AssetJobIdsIn,
    AssetJobOut,
    AssetOut,
    AssetRenameIn,
)
from liberastra.storage import resolve

router = APIRouter(prefix="/assets", tags=["assets"])


def _get_owned(db, asset_id: int, user: User) -> Asset:  # noqa: ANN001
    record = db.get(Asset, asset_id)
    if record is None or record.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资产不存在")
    return record


def _download_name(record: Asset) -> str:
    """下载文件名：日期 + 自定义名称或提示词摘要；都没有时退回落盘文件名。"""
    base = Path(record.path).name
    meta = record.meta or {}
    summary = meta.get("name") or meta.get("prompt") or meta.get("text") or meta.get("title")
    if not summary:
        return base
    slug = re.sub(r'[\\/:*?"<>|\s]+', "_", str(summary)).strip("_")[:24]
    if not slug:
        return base
    date = record.created_at.strftime("%Y%m%d")
    return f"{date}_{slug}{Path(record.path).suffix}"


@router.get("", response_model=list[AssetOut])
def list_assets(
    user: CurrentUser,
    db: DbSession,
    kind: str | None = None,
    job_id: str | None = None,
    job_kind: str | None = None,
    job_function: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_hidden: bool = False,
) -> list[Asset]:
    stmt = select(Asset).where(Asset.owner_id == user.id).order_by(Asset.created_at.desc())
    if not include_hidden:
        stmt = stmt.where(Asset.hidden.is_(False))
    if kind:
        kinds = [k.strip() for k in kind.split(",") if k.strip()]
        stmt = stmt.where(Asset.kind.in_(kinds))
    if job_id:
        stmt = stmt.where(Asset.job_id == job_id)
    if job_kind or job_function:
        stmt = stmt.join(Job, Asset.job_id == Job.id)
    if job_kind:
        job_kinds = [k.strip() for k in job_kind.split(",") if k.strip()]
        stmt = stmt.where(Job.kind.in_(job_kinds))
    if job_function:
        functions = [f.strip() for f in job_function.split(",") if f.strip()]
        stmt = stmt.where(Job.function.in_(functions))
    return list(
        db.scalars(
            stmt.offset(max(0, offset)).limit(min(max(limit, 1), 200))
        ).all()
    )


@router.get("/jobs", response_model=list[AssetJobOut])
def list_asset_jobs(
    user: CurrentUser,
    db: DbSession,
    job_kind: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[AssetJobOut]:
    """素材库「工作」页签：按 job 聚合可见资源，不生成缩略图。"""
    conditions = [
        Asset.owner_id == user.id,
        Asset.hidden.is_(False),
        Job.owner_id == user.id,
    ]
    if job_kind:
        kinds = [k.strip() for k in job_kind.split(",") if k.strip()]
        if kinds:
            conditions.append(Job.kind.in_(kinds))
    stmt = (
        select(
            Job.id,
            Job.kind,
            Job.created_at,
            func.count(Asset.id).label("asset_count"),
        )
        .join(Asset, Asset.job_id == Job.id)
        .where(*conditions)
        .group_by(Job.id, Job.kind, Job.created_at)
        .order_by(Job.created_at.desc(), Job.id.desc())
        .offset(max(0, offset))
        .limit(min(max(limit, 1), 100))
    )
    rows = db.execute(stmt).all()
    job_ids = [row[0] for row in rows]
    kinds_by_job: dict[str, set[str]] = {}
    if job_ids:
        kind_rows = db.execute(
            select(Asset.job_id, Asset.kind)
            .where(
                Asset.owner_id == user.id,
                Asset.hidden.is_(False),
                Asset.job_id.in_(job_ids),
            )
            .distinct()
        ).all()
        for row in kind_rows:
            kinds_by_job.setdefault(row[0], set()).add(row[1])
    return [
        AssetJobOut(
            job_id=row[0],
            job_kind=row[1],
            created_at=row[2],
            asset_count=int(row[3]),
            kinds=sorted(kinds_by_job.get(row[0], set())),
        )
        for row in rows
    ]


def _jobs_for_owner(db, owner_id: int, job_ids: list[str]) -> list[Job]:  # noqa: ANN001
    wanted = list(dict.fromkeys(job_ids))
    jobs = db.scalars(
        select(Job).where(Job.id.in_(wanted), Job.owner_id == owner_id)
    ).all()
    by_id = {job.id: job for job in jobs}
    if len(by_id) != len(wanted):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或无权访问")
    return [by_id[job_id] for job_id in wanted]


def _owned_jobs(db, user: User, job_ids: list[str]) -> list[Job]:  # noqa: ANN001
    return _jobs_for_owner(db, user.id, job_ids)


def _safe_zip_part(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", value).strip(" .")
    return cleaned or fallback


def _job_folder_name(job: Job) -> str:
    created = job.created_at or datetime.now(UTC)
    kind = _safe_zip_part(job.kind, "job")[:40]
    return f"{created:%Y%m%d-%H%M%S}_{kind}_{job.id[:8]}"


def _unique_zip_name(name: str, used: set[str]) -> str:
    safe = _safe_zip_part(name, "asset")
    if safe not in used:
        used.add(safe)
        return safe
    path = Path(safe)
    index = 2
    while True:
        candidate = f"{path.stem} ({index}){path.suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        index += 1


def _build_jobs_zip(db, owner_id: int, job_ids: list[str]) -> FileResponse:  # noqa: ANN001
    jobs = _jobs_for_owner(db, owner_id, job_ids)
    assets = db.scalars(
        select(Asset)
        .where(
            Asset.owner_id == owner_id,
            Asset.job_id.in_([job.id for job in jobs]),
            Asset.hidden.is_(False),
        )
        .order_by(Asset.created_at)
    ).all()
    by_job: dict[str, list[Asset]] = {}
    for asset in assets:
        by_job.setdefault(str(asset.job_id), []).append(asset)

    handle, zip_name = tempfile.mkstemp(prefix="liberastra-jobs-", suffix=".zip")
    os.close(handle)
    added = 0
    missing: list[str] = []
    try:
        with zipfile.ZipFile(zip_name, "w", compression=zipfile.ZIP_STORED) as archive:
            for job in jobs:
                folder = _job_folder_name(job)
                used: set[str] = set()
                for asset in by_job.get(job.id, []):
                    path = resolve(asset.path)
                    if not path.is_file():
                        missing.append(f"{folder}/{Path(asset.path).name}")
                        continue
                    name = _unique_zip_name(Path(asset.path).name, used)
                    archive.write(path, f"{folder}/{name}")
                    added += 1
            if missing:
                archive.writestr("missing.txt", "\n".join(missing))
        if added == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有可下载的产物")
    except Exception:
        os.unlink(zip_name)
        raise
    return FileResponse(
        zip_name,
        media_type="application/zip",
        filename=f"liberastra-jobs-{datetime.now(UTC):%Y%m%d-%H%M%S}.zip",
        background=BackgroundTask(os.unlink, zip_name),
    )


@router.post("/jobs/download")
def download_asset_jobs(
    body: AssetJobIdsIn,
    user: CurrentUser,
    db: DbSession,
) -> FileResponse:
    """把选中的任务文件夹打成 ZIP；只打包可见资产，保留任务子目录。"""
    return _build_jobs_zip(db, user.id, body.job_ids)


@router.post("/jobs/download-token")
def create_jobs_download_token(
    body: AssetJobIdsIn,
    user: CurrentUser,
    db: DbSession,
) -> dict[str, str]:
    jobs = _owned_jobs(db, user, body.job_ids)
    token = create_download_token(
        str(user.id),
        kind="jobs",
        payload={"job_ids": [job.id for job in jobs]},
    )
    return {"url": f"/api/v1/assets/jobs/download?token={quote(token)}"}


@router.get("/jobs/download")
def download_jobs_with_token(token: str, db: DbSession) -> FileResponse:
    payload = decode_download_token(token)
    if payload is None or payload.get("kind") != "jobs":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="下载链接无效或已过期")
    job_ids = payload.get("job_ids")
    if not isinstance(job_ids, list) or not job_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="下载链接无效")
    try:
        owner_id = int(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="下载链接无效"
        ) from exc
    return _build_jobs_zip(db, owner_id, [str(job_id) for job_id in job_ids])


@router.post("/jobs/delete", response_model=AssetJobDeleteOut)
def delete_asset_jobs(
    body: AssetJobIdsIn,
    user: CurrentUser,
    db: DbSession,
) -> AssetJobDeleteOut:
    """删除选中的任务文件夹：资产、文件、缩略图和任务记录一起删除。"""
    jobs = _owned_jobs(db, user, body.job_ids)
    active = [job for job in jobs if job.status not in TERMINAL_STATUSES]
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="有任务仍在进行中，完成或取消后才能删除",
        )

    job_ids = [job.id for job in jobs]
    assets = db.scalars(select(Asset).where(Asset.job_id.in_(job_ids))).all()
    for asset in assets:
        try:
            resolve(asset.path).unlink(missing_ok=True)
        except ValueError:
            pass
        remove_asset_thumb(asset.id)
        db.delete(asset)
    for job in jobs:
        try:
            output_dir = resolve(f"outputs/{job.id}")
            if output_dir.is_dir():
                shutil.rmtree(output_dir)
            elif output_dir.exists():
                output_dir.unlink(missing_ok=True)
        except ValueError:
            pass
        db.delete(job)
    db.commit()
    return AssetJobDeleteOut(jobs=len(jobs), assets=len(assets))


@router.post("/{asset_id}/publish", response_model=AssetOut)
def publish_asset(asset_id: int, user: CurrentUser, db: DbSession) -> Asset:
    """发布画布中间结果：取消隐藏,摘掉 canvas_temp 标记(保留 canvas_id/node 溯源)。"""
    record = _get_owned(db, asset_id, user)
    record.hidden = False
    meta = dict(record.meta or {})
    meta.pop("canvas_temp", None)
    record.meta = meta
    db.commit()
    db.refresh(record)
    return record


@router.post("/{asset_id}/download-token")
def create_asset_download_token(
    asset_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict[str, str]:
    record = _get_owned(db, asset_id, user)
    token = create_download_token(
        str(user.id),
        kind="asset",
        payload={"asset_id": record.id},
    )
    return {"url": f"/api/v1/assets/{asset_id}/download?token={quote(token)}"}


@router.get("/{asset_id}/download")
def download_asset_with_token(asset_id: int, token: str, db: DbSession) -> FileResponse:
    payload = decode_download_token(token)
    if (
        payload is None
        or payload.get("kind") != "asset"
        or int(payload.get("asset_id", 0)) != asset_id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="下载链接无效或已过期")
    record = db.get(Asset, asset_id)
    if record is None or str(record.owner_id) != str(payload.get("sub")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资产不存在")
    try:
        path = resolve(record.path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法路径") from exc
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件已丢失")
    return FileResponse(path, media_type=record.mime, filename=_download_name(record))


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: int, user: CurrentUser, db: DbSession) -> Asset:
    return _get_owned(db, asset_id, user)


_NAME_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


@router.patch("/{asset_id}", response_model=AssetOut)
def rename_asset(asset_id: int, body: AssetRenameIn, user: CurrentUser, db: DbSession) -> Asset:
    """只改展示名，不改落盘文件。空名称会去掉自定义名字，列表回到提示词或「未命名」。"""
    name = " ".join(body.name.split())
    if len(name) > 80:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="名称最长 80 个字")
    if name and _NAME_FORBIDDEN.search(name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="名称不能包含 \\ / : * ? \" < > |",
        )
    record = _get_owned(db, asset_id, user)
    meta = dict(record.meta or {})
    if name:
        meta["name"] = name
    else:
        meta.pop("name", None)
    record.meta = meta
    db.commit()
    db.refresh(record)
    return record


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


# 不能用 immutable：浏览器会把第一次的彩色缩略图缓存一年，源文件换成深度图后小图不会更新。
_THUMB_CACHE = {"Cache-Control": "private, no-cache"}


@router.get("/{asset_id}/thumb")
async def asset_thumb(asset_id: int, user: CurrentUser, db: DbSession) -> FileResponse:
    """列表和画布用的小图。图片和视频各一张 WebP，其它类型没有缩略图。"""
    record = _get_owned(db, asset_id, user)
    if record.kind not in ("image", "video"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="这个类型没有缩略图")
    try:
        src = resolve(record.path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法路径") from exc
    if not src.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件已丢失")
    dest = asset_thumb_path(record.id, src)
    if not (dest.exists() and dest.stat().st_size > 0):
        try:
            if record.kind == "image":
                data = await asyncio.to_thread(image_thumb_bytes, src)
                dest = await asyncio.to_thread(store_asset_thumb, record.id, data, src)
            else:
                await asyncio.to_thread(extract_video_thumb, src, dest)
                await asyncio.to_thread(remove_asset_thumb, record.id, keep=dest)
        except ProviderError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return FileResponse(dest, media_type="image/webp", headers=_THUMB_CACHE)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int, user: CurrentUser, db: DbSession) -> None:
    record = _get_owned(db, asset_id, user)
    try:
        resolve(record.path).unlink(missing_ok=True)
    except ValueError:
        pass
    remove_asset_thumb(record.id)
    db.delete(record)
    db.commit()
