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
    group: str = ""  # local | api，服务提供方页面的左栏分类


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


@dataclass(frozen=True)
class MediaSlotSpec:
    """一个媒体输入槽：决定功能页上传框数量，以及画布要补几个前置节点。"""

    key: str
    type: str  # image | video | audio | text
    label: str
    required: bool = True
    multiple: bool = False
    input_kind: str = ""  # 画布补建用。动作迁移的人物图是 character


@dataclass(frozen=True)
class ExecutionSpec:
    """ComfyUI 工作流包与云端模型共用的执行契约。"""

    target_type: str  # workflow | model
    target_id: str
    display_name: str
    sub_capability: str
    provider_type: str
    provider_id: int | None = None
    provider_name: str = ""
    category: str = ""  # image | video | speech | llm
    media_slots: tuple[MediaSlotSpec, ...] = ()
    inputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_type": self.target_type,
            "target_id": self.target_id,
            "display_name": self.display_name,
            "sub_capability": self.sub_capability,
            "provider_type": self.provider_type,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "category": self.category,
            "media_slots": [
                {
                    "key": slot.key,
                    "type": slot.type,
                    "label": slot.label,
                    "required": slot.required,
                    "multiple": slot.multiple,
                    "input_kind": slot.input_kind or slot.type,
                }
                for slot in self.media_slots
            ],
            "inputs": self.inputs,
        }
