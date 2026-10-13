"""Job 的请求/响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    progress: float
    provider_id: int | None
    model: str | None
    params: dict
    steps: list
    outputs: list
    error: str | None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}
