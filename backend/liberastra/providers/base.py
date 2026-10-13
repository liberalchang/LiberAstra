"""Provider 适配层基础：类型元数据、协议、错误。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ProviderError(Exception):
    """Provider 调用失败（网络、鉴权、协议、响应格式）。"""


@dataclass(frozen=True)
class ProviderTypeInfo:
    """注册表中的一类 Provider，前端据此渲染添加表单。"""

    type: str
    label: str
    capabilities: tuple[str, ...]
    requires_api_key: bool
    default_base_url: str | None = None
    description: str = ""


class LLMAdapter(Protocol):
    """LLM 能力协议。"""

    async def chat(self, *, model: str, messages: list[dict[str, Any]], **params: Any) -> str: ...

    async def list_models(self) -> list[str]: ...

    async def test(self) -> str: ...
