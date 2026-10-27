"""通用上传：先存文件拿到相对路径，供后续任务参数（如 BGM）引用。

as_asset=true 时同时建档为 Asset（画布输入节点直接引用资产）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.models.asset import ASSET_KINDS
from liberastra.storage import create_asset, save_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadOut(BaseModel):
    path: str
    size: int
    asset_id: int | None = None


@router.post("", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
async def upload(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    as_asset: bool = False,
    kind: str = "image",
    hidden: bool = False,
) -> UploadOut:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空文件")
    path = save_upload(file.filename or "upload.bin", content)
    asset_id: int | None = None
    if as_asset:
        if kind not in ASSET_KINDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的资产类型: {kind}"
            )
        asset = create_asset(
            db,
            kind=kind,
            rel_path=path,
            owner_id=user.id,
            hidden=hidden,
            meta={"source": "canvas-upload", "source_name": file.filename or ""},
        )
        asset_id = asset.id
    return UploadOut(path=path, size=len(content), asset_id=asset_id)
