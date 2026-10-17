"""Provider 类型注册表。新增 Provider 类型时在此登记。"""

from __future__ import annotations

from liberastra.providers.base import (
    ASRAdapter,
    LLMAdapter,
    ProviderError,
    ProviderTypeInfo,
    TTSAdapter,
)

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
    "openai_tts": ProviderTypeInfo(
        type="openai_tts",
        label="OpenAI 兼容 TTS",
        capabilities=("tts",),
        requires_api_key=False,
        default_base_url="http://localhost:8880/v1",
        description="标准 /v1/audio/speech：OpenAI / SiliconFlow / Kokoro-FastAPI / Speaches",
    ),
    "edge_tts": ProviderTypeInfo(
        type="edge_tts",
        label="本地（微软 Edge TTS）",
        capabilities=("tts",),
        requires_api_key=False,
        default_base_url="",
        description="本机 edge-tts（≥7.3.1，Sec-MS-GEC v2）。零配置在线合成，仅 mp3",
    ),
    "openai_stt": ProviderTypeInfo(
        type="openai_stt",
        label="OpenAI 兼容 ASR",
        capabilities=("asr",),
        requires_api_key=False,
        default_base_url="http://localhost:8100/v1",
        description="标准 /v1/audio/transcriptions：OpenAI / Groq / Speaches / faster-whisper-server",
    ),
    "liber_speech": ProviderTypeInfo(
        type="liber_speech",
        label="Liber Speech API",
        capabilities=("tts", "asr"),
        requires_api_key=False,
        default_base_url="http://127.0.0.1:5555",
        description=(
            "本仓库 services/speech。可单独部署在局域网显卡主机。Base URL 填 http://<主机IP>:5555，"
            "音色名填语言代码如 zh、en。服务若设置了 LIBER_SPEECH_API_KEY，把同一个 Key 填到这里。"
        ),
    ),
    "comfyui": ProviderTypeInfo(
        type="comfyui",
        label="ComfyUI",
        capabilities=("image", "video", "tts"),
        requires_api_key=False,
        default_base_url="http://localhost:8188",
        description="局域网 ComfyUI 实例，工作流包驱动（文生图/图生图/修复放大/视频/语音工作流）",
    ),
    "openai_images": ProviderTypeInfo(
        type="openai_images",
        label="OpenAI 兼容图像",
        capabilities=("image",),
        requires_api_key=False,
        default_base_url="https://api.openai.com/v1",
        description="标准 /v1/images/*：OpenAI gpt-image 及 BananaRouter 类兼容网关",
    ),
}

__all__ = [
    "ASRAdapter",
    "LLMAdapter",
    "PROVIDER_TYPES",
    "ProviderError",
    "ProviderTypeInfo",
    "TTSAdapter",
]
