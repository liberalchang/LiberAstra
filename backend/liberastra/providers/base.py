"""Provider 适配层基础：类型元数据、协议、错误。"""

from __future__ import annotations

from dataclasses import dataclass, field
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


class TTSAdapter(Protocol):
    """TTS 能力协议。synthesize 返回音频字节。"""

    async def synthesize(
        self,
        *,
        text: str,
        voice: str,
        model: str | None = None,
        fmt: str = "mp3",
        **params: Any,
    ) -> bytes: ...

    async def list_voices(self) -> list[str]: ...

    async def test(self) -> str: ...


@dataclass
class ASRSegment:
    start: float  # 秒
    end: float
    text: str


@dataclass
class ASRResult:
    text: str
    segments: list[ASRSegment] = field(default_factory=list)
    language: str | None = None


class ASRAdapter(Protocol):
    """ASR 能力协议。平台层统一输出分段时间戳。"""

    async def transcribe(
        self,
        *,
        file_path: str,
        language: str | None = None,
        task: str = "transcribe",
        model: str | None = None,
        **params: Any,
    ) -> ASRResult: ...

    async def test(self) -> str: ...
