"""本机工具 API：拼接任务和工具注册表。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.api.utils import wait_for_job
from liberastra.models import Asset, Job
from liberastra.schemas.job import JobOut
from liberastra.services.native_tools import tool_specs

router = APIRouter(prefix="/tools", tags=["tools"])


class ConcatRequest(BaseModel):
    kind: Literal["image", "video", "audio"]
    asset_ids: list[int] = Field(min_length=1)
    layout: Literal["horizontal", "vertical", "grid"] = "horizontal"
    columns: int = Field(default=2, ge=1, le=16)
    gap: int = Field(default=4, ge=0, le=256)
    gap_color: str = "#FFFFFF"


def _validated_assets(db: Session, owner_id: int, body: ConcatRequest) -> None:
    if body.kind == "image" and len(body.asset_ids) < 2:
        raise HTTPException(status_code=400, detail="图片拼接至少需要两张输入")
    for asset_id in body.asset_ids:
        asset = db.get(Asset, asset_id)
        if asset is None or asset.owner_id != owner_id:
            raise HTTPException(status_code=400, detail=f"素材不存在: {asset_id}")
        if asset.kind != body.kind:
            raise HTTPException(
                status_code=400,
                detail=f"素材 {asset_id} 类型是 {asset.kind}，与拼接类型 {body.kind} 不符",
            )


@router.get("")
def list_tools(user: CurrentUser) -> list[dict]:
    del user
    return [spec.to_dict() for spec in tool_specs()]


@router.post("/concat", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def concat(
    body: ConcatRequest,
    user: CurrentUser,
    db: DbSession,
    request: Request,
    wait: bool = False,
) -> Job:
    _validated_assets(db, user.id, body)
    job = request.app.state.jobs.submit(
        db,
        owner_id=user.id,
        kind="media.concat",
        params={
            "kind": body.kind,
            "asset_ids": body.asset_ids,
            "layout": body.layout,
            "columns": body.columns,
            "gap": body.gap,
            "gap_color": body.gap_color,
            "visible": True,
            "tool_id": f"{body.kind}_concat",
        },
    )
    if wait:
        return await wait_for_job(db, job.id)
    return job
