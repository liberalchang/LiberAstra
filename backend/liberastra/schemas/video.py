"""视频请求模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class QuickVideoRequest(BaseModel):
    topic: str | None = Field(default=None, max_length=2000)
    script: str | None = Field(default=None, max_length=100_000)  # 固定文案（优先于 topic）
    split_mode: str = Field(default="paragraph", pattern="^(paragraph|line|sentence)$")
    storyboard_count: int = Field(default=4, ge=1, le=12)
    aspect: str = Field(default="9:16", pattern="^(9:16|1:1|16:9)$")
    voice: str = ""
    voice_record_id: int | None = None
    style_prefix: str = ""
    storyboard: dict[str, Any] | None = None  # 提供则跳过 LLM（分镜编辑器回传）
    storyboard_only: bool = False  # 只生成脚本与分镜
    llm_provider_id: int | None = None
    tts_provider_id: int | None = None
    image_provider_id: int | None = None
    image_workflow: str | None = None
    image_inputs: dict[str, Any] = Field(default_factory=dict)
    bgm_path: str | None = None
    bgm_volume: float = Field(default=0.2, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_input(self) -> QuickVideoRequest:
        if self.storyboard is None and not self.topic and not self.script:
            raise ValueError("topic、script、storyboard 至少提供一个")
        return self
