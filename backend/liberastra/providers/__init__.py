"""Provider 类型注册表。新增 Provider 类型时在此登记。"""

from __future__ import annotations

from liberastra.providers.base import LLMAdapter, ProviderError, ProviderTypeInfo

PROVIDER_TYPES: dict[str, ProviderTypeInfo] = {
    "openai_compatible": ProviderTypeInfo(
        type="openai_compatible",
        label="OpenAI 兼容服务",
        capabilities=("llm",),
        requires_api_key=False,
        default_base_url="http://localhost:8000/v1",
        description="覆盖 vLLM / LM Studio / DeepSeek / 通义 / 火山方舟 / Kimi / 智谱 等",
    ),
    "ollama": ProviderTypeInfo(
        type="ollama",
        label="Ollama",
        capabilities=("llm",),
        requires_api_key=False,
        default_base_url="http://localhost:11434",
        description="本地 Ollama：/api/tags 拉取模型列表与健康检查，chat 走 /v1 兼容端点",
    ),
}

__all__ = ["LLMAdapter", "PROVIDER_TYPES", "ProviderError", "ProviderTypeInfo"]
