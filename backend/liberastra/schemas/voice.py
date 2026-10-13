"""Voice 音色库响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class VoiceOut(BaseModel):
    id: int
    name: str
    provider_id: int | None
    voice_id: str | None
    ref_audio_path: str | None
    ref_text: str | None
    tags: list[str]
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}
