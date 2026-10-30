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
        description="覆盖 vLLM / LM Studio / DeepSeek / 通义 / Kimi / 智谱等 OpenAI 兼容对话接口",
        group="api",
    ),
    "volcengine_ark": ProviderTypeInfo(
        type="volcengine_ark",
        label="火山方舟",
        capabilities=("llm", "image", "video"),
        requires_api_key=False,
        default_base_url="https://ark.cn-beijing.volces.com/api/v3",
        description="火山方舟：对话与视觉、Seedream 图像、Seedance 视频。一个 ARK API Key。",
        group="api",
    ),
    "volcengine_speech": ProviderTypeInfo(
        type="volcengine_speech",
        label="火山豆包语音",
        capabilities=("tts", "asr"),
        requires_api_key=False,
        default_base_url="https://openspeech.bytedance.com",
        description="豆包语音合成与识别。密钥与火山方舟分开填写。",
        group="api",
    ),
    "anthropic": ProviderTypeInfo(
        type="anthropic",
        label="Anthropic",
        capabilities=("llm",),
        requires_api_key=False,
        default_base_url="https://api.anthropic.com",
        description=(
            "Claude Messages API：POST /v1/messages，模型列表 GET /v1/models。"
            "密钥在 platform.claude.com 申请。"
        ),
        group="api",
    ),
    "google": ProviderTypeInfo(
        type="google",
        label="Google",
        capabilities=("llm",),
        requires_api_key=False,
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        description="Gemini 官方 OpenAI 兼容接口。密钥在 Google AI Studio 申请，请求头使用 Bearer。",
        group="api",
    ),
    "openai": ProviderTypeInfo(
        type="openai",
        label="OpenAI",
        capabilities=("llm",),
        requires_api_key=False,
        default_base_url="https://api.openai.com/v1",
        description="OpenAI Platform：POST /v1/chat/completions，模型列表 GET /v1/models。",
        group="api",
    ),
    "chatgpt": ProviderTypeInfo(
        type="chatgpt",
        label="ChatGPT",
        capabilities=("llm",),
        requires_api_key=False,
        default_base_url="https://api.openai.com/v1",
        description=(
            "ChatGPT 对话模型，走 OpenAI 官方 Chat Completions。"
            "密钥与 OpenAI 卡片相同，在 platform.openai.com 申请。"
        ),
        group="api",
    ),
    "deepseek": ProviderTypeInfo(
        type="deepseek",
        label="DeepSeek",
        capabilities=("llm",),
        requires_api_key=False,
        default_base_url="https://api.deepseek.com",
        description="DeepSeek 官方 OpenAI 兼容接口：/chat/completions 与 /models。",
        group="api",
    ),
    "kimi_code": ProviderTypeInfo(
        type="kimi_code",
        label="Kimi Code",
        capabilities=("llm",),
        requires_api_key=False,
        default_base_url="https://api.kimi.com/coding/v1",
        description=(
            "Kimi Code 官方 OpenAI 兼容接口。海外可把地址改成 https://api.kimi.ai/coding/v1。"
            "密钥在 Kimi Code 控制台申请。"
        ),
        group="api",
    ),
    "aliyun_bailian": ProviderTypeInfo(
        type="aliyun_bailian",
        label="阿里云百炼",
        capabilities=("llm",),
        requires_api_key=False,
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="百炼千问的 OpenAI 兼容接口。有业务空间 ID 时，可改成 https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1。",
        group="api",
    ),
    "ollama": ProviderTypeInfo(
        type="ollama",
        label="Ollama",
        capabilities=("llm",),
        requires_api_key=False,
        default_base_url="http://localhost:11434",
        description="本地 Ollama：/api/tags 拉取模型列表与健康检查，chat 走 /v1 兼容端点",
        group="local",
    ),
    "openai_tts": ProviderTypeInfo(
        type="openai_tts",
        label="OpenAI 兼容 TTS",
        capabilities=("tts",),
        requires_api_key=False,
        default_base_url="http://localhost:8880/v1",
        description="标准 /v1/audio/speech：OpenAI / SiliconFlow / Kokoro-FastAPI / Speaches",
        group="api",
    ),
    "edge_tts": ProviderTypeInfo(
        type="edge_tts",
        label="本地（微软 Edge TTS）",
        capabilities=("tts",),
        requires_api_key=False,
        default_base_url="",
        description="本机 edge-tts（≥7.3.1，Sec-MS-GEC v2）。零配置在线合成，仅 mp3",
        group="local",
    ),
    "openai_stt": ProviderTypeInfo(
        type="openai_stt",
        label="OpenAI 兼容 ASR",
        capabilities=("asr",),
        requires_api_key=False,
        default_base_url="http://localhost:8100/v1",
        description="标准 /v1/audio/transcriptions：OpenAI / Groq / Speaches / faster-whisper-server",
        group="api",
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
        group="local",
    ),
    "liber_depth": ProviderTypeInfo(
        type="liber_depth",
        label="Liber Depth 深度图",
        capabilities=("depth",),
        requires_api_key=False,
        default_base_url="http://127.0.0.1:5556",
        description=(
            "本仓库 services/depth 深度图插件服务。可安装在本地或部署在局域网显卡主机"
            "（http://<主机IP>:5556），使用 MiDaS 模型将图片转为深度图。"
        ),
        group="local",
    ),
    "comfyui": ProviderTypeInfo(
        type="comfyui",
        label="ComfyUI",
        capabilities=("image", "video", "tts"),
        requires_api_key=False,
        default_base_url="http://localhost:8188",
        description="局域网 ComfyUI 实例，工作流包驱动（文生图/图生图/修复放大/视频/语音工作流）",
        group="local",
    ),
    "openai_images": ProviderTypeInfo(
        type="openai_images",
        label="OpenAI 兼容图像",
        capabilities=("image",),
        requires_api_key=False,
        default_base_url="https://api.openai.com/v1",
        description="标准 /v1/images/*：OpenAI gpt-image 及 BananaRouter 类兼容网关",
        group="api",
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
