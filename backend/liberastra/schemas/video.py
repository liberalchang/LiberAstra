"""视频请求模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class QuickVideoRequest(BaseModel):
    topic: str | None = Field(default=None, max_length=2000)
    script: str | None = Field(default=None, max_length=100_000)  # 固定文案（优先于 topic）
    title: str = Field(default="", max_length=200)  # 视频标题：固定显示在模板里；AI 创作时缺省用主题
    split_mode: str = Field(default="paragraph", pattern="^(paragraph|line|sentence)$")
    storyboard_count: int = Field(default=4, ge=1, le=12)
    aspect: str = Field(default="9:16", pattern="^(9:16|1:1|16:9)$")
    voice: str = ""
    voice_record_id: int | None = None
    language: str = ""  # Liber Speech 的 language_id；空则按音色名猜测
    character_id: int | None = None
    style_prefix: str = ""
    storyboard: dict[str, Any] | None = None  # 提供则跳过 LLM（分镜编辑器回传）
    storyboard_only: bool = False  # 只生成脚本与分镜
    # 是否用脚本服务 LLM 把口播改写成画面提示词（image/video 模板）；关则 visual=口播原文。
    # 与工作流包内的 Guide 无关：Guide 只由所选包决定。
    optimize_visuals: bool = True
    llm_provider_id: int | None = None
    llm_model: str = ""  # LLM 服务里的具体模型；空则用 Provider 配置的默认模型
    tts_provider_id: int | None = None
    image_provider_id: int | None = None
    video_provider_id: int | None = None
    image_workflow: str | None = None
    image_inputs: dict[str, Any] = Field(default_factory=dict)
    # 分镜模板：名 + 类型决定分镜画面来源（static 静态 / image 插图 / video 视频）
    template: str = ""
    # comfyui 语音工作流（配音 Provider 为 comfyui 时必传）
    tts_workflow: str | None = None
    tts_inputs: dict[str, Any] = Field(default_factory=dict)
    # video_* 模板：逐镜视频工作流（视频 Provider 为 comfyui 时必传）
    video_workflow: str | None = None
    video_inputs: dict[str, Any] = Field(default_factory=dict)
    bgm_path: str | None = None
    bgm_volume: float = Field(default=0.2, ge=0.0, le=1.0)
    # custom：逐镜配音。auto：仅文生视频模板保留模型音轨。
    audio_mode: str = Field(default="custom", pattern="^(custom|auto)$")
    # 文字显隐与字号：模板标题/文案（倍率），视频烧录字幕（字号，0=默认）
    show_title: bool = True
    show_text: bool = True
    show_subtitle: bool = True
    title_scale: float = Field(default=1.0, ge=0.3, le=3.0)
    text_scale: float = Field(default=1.0, ge=0.3, le=3.0)
    subtitle_size: float = Field(default=0, ge=0, le=128)
    subtitle_color: str = Field(default="", pattern="^$|^#[0-9a-fA-F]{6}$")  # 如 #FFFF00；空=白色默认

    @model_validator(mode="after")
    def _check_input(self) -> QuickVideoRequest:
        if self.storyboard is None and not self.topic and not self.script:
            raise ValueError("topic、script、storyboard 至少提供一个")
        return self
