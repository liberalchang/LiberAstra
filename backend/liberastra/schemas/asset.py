"""Asset 响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AssetOut(BaseModel):
    id: int
    kind: str
    path: str
    mime: str | None
    size: int
    job_id: str | None
    meta: dict
    hidden: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AssetJobOut(BaseModel):
    """素材库「工作」页签：一次任务的可见资源摘要。"""

    job_id: str
    job_kind: str
    created_at: datetime
    asset_count: int
    kinds: list[str]


class AssetRenameIn(BaseModel):
    """预览里修改的展示名。空字符串表示去掉自定义名称。"""

    name: str
