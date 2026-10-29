"""各家官方文档里仍在使用的模型 ID。刷新列表后，远端多出来的模型会并进目录。"""

from __future__ import annotations

from liberastra.providers.catalog import model_item

# openai 与 chatgpt 共用 Platform API，卡片按产品分开。
CLOUD_TYPES = (
    "anthropic",
    "google",
    "openai",
    "chatgpt",
    "deepseek",
    "kimi_code",
    "aliyun_bailian",
)

_CHAT = ["chat"]
_CHAT_VISION = ["chat", "vision"]


def _llm(model_id: str, label: str, *, subs: list[str] | None = None, enabled: bool = True) -> dict:
    return model_item(
        model_id,
        label=label,
        category="llm",
        sub_capabilities=subs or _CHAT,
        enabled=enabled,
    )


CLOUD_PRESETS: dict[str, list[dict]] = {
    "anthropic": [
        _llm("claude-sonnet-4-6", "Claude Sonnet 4.6", subs=_CHAT_VISION),
        _llm("claude-opus-4-6", "Claude Opus 4.6", subs=_CHAT_VISION, enabled=False),
        _llm("claude-haiku-4-5", "Claude Haiku 4.5", subs=_CHAT_VISION, enabled=False),
    ],
    "google": [
        _llm("gemini-2.5-flash", "Gemini 2.5 Flash", subs=_CHAT_VISION),
        _llm("gemini-2.5-pro", "Gemini 2.5 Pro", subs=_CHAT_VISION, enabled=False),
    ],
    "openai": [
        _llm("gpt-4o", "GPT-4o", subs=_CHAT_VISION),
        _llm("gpt-4o-mini", "GPT-4o mini", enabled=False),
    ],
    "chatgpt": [
        _llm("gpt-4o", "GPT-4o", subs=_CHAT_VISION),
        _llm("gpt-4o-mini", "GPT-4o mini", enabled=False),
    ],
    "deepseek": [
        _llm("deepseek-chat", "DeepSeek Chat"),
        _llm("deepseek-reasoner", "DeepSeek Reasoner", enabled=False),
    ],
    "kimi_code": [
        _llm("k3.1-pro", "K3.1 Pro", subs=_CHAT_VISION),
        _llm("kimi-for-coding", "Kimi for Coding", subs=_CHAT_VISION, enabled=False),
        _llm("k3", "K3", subs=_CHAT_VISION, enabled=False),
    ],
    "aliyun_bailian": [
        _llm("qwen-plus", "Qwen Plus"),
        _llm("qwen-max", "Qwen Max", enabled=False),
        _llm("qwen-vl-plus", "Qwen VL Plus", subs=_CHAT_VISION, enabled=False),
    ],
}


def presets_for(provider_type: str) -> list[dict]:
    rows = CLOUD_PRESETS.get(provider_type) or []
    return [dict(item) for item in rows]
