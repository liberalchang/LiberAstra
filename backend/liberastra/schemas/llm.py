"""LLM 聊天请求模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    provider_id: int | None = None  # 缺省用第一个启用的 LLM Provider
    model: str = Field(min_length=1)
    messages: list[dict[str, Any]] = Field(min_length=1)
    options: dict[str, Any] = Field(default_factory=dict)  # temperature 等透传参数
