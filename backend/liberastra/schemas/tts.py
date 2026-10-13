"""TTS / ASR 请求模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

TTS_FORMATS = ("mp3", "wav", "ogg_opus")


class TTSRequest(BaseModel):
    provider_id: int | None = None
    voice_record_id: int | None = None  # 音色库条目；优先于 voice
    voice: str = ""  # Provider 侧音色名（如 zh-CN-XiaoxiaoNeural、alloy）
    model: str | None = None
    text: str = Field(min_length=1, max_length=100_000)
    format: str = Field(default="mp3", pattern="^(mp3|wav|ogg_opus)$")
    options: dict[str, Any] = Field(default_factory=dict)


class OpenAISpeechRequest(BaseModel):
    """OpenAI 兼容 /v1/audio/speech 请求。"""

    model: str = "tts-1"
    input: str = Field(min_length=1, max_length=100_000)
    voice: str
    response_format: str = Field(default="mp3", pattern="^(mp3|wav|ogg_opus|opus|aac|flac)$")
    speed: float | None = Field(default=None, gt=0.25, le=4.0)
