"""角色库响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CharacterOut(BaseModel):
    id: int
    name: str
    description: str
    portrait_path: str | None
    turnaround_path: str | None
    front_path: str | None
    side_path: str | None
    back_path: str | None
    voice_record_id: int | None
    voice_name: str | None
    tags: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}
