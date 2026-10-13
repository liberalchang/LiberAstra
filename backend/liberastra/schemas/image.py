"""图像请求模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):
    provider_id: int | None = None
    workflow: str | None = None  # ComfyUI 工作流包名（comfyui 类型必填）
    prompt: str = ""
    negative_prompt: str = ""
    width: int = Field(default=1024, ge=64, le=4096)
    height: int = Field(default=1024, ge=64, le=4096)
    steps: int | None = Field(default=None, ge=1, le=150)
    seed: int = Field(default=-1, description="-1 表示随机")
    n: int = Field(default=1, ge=1, le=8)
    inputs: dict[str, Any] = Field(default_factory=dict)  # 额外工作流参数
    options: dict[str, Any] = Field(default_factory=dict)


class PromptOptimizeRequest(BaseModel):
    provider_id: int | None = None
    prompt: str = Field(min_length=1, max_length=4000)


class PromptOptimizeResponse(BaseModel):
    optimized: str
