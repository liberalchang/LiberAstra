"""Provider 服务：密钥加解密、适配器构造、连接测试、模型拉取。"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from liberastra.core.security import get_fernet
from liberastra.models import Provider
from liberastra.providers.asr.openai_stt import OpenAISTT
from liberastra.providers.base import ProviderError
from liberastra.providers.image.comfyui import ComfyUIImage
from liberastra.providers.image.openai_images import OpenAIImages
from liberastra.providers.llm.ollama import OllamaLLM
from liberastra.providers.llm.openai_compatible import OpenAICompatibleLLM
from liberastra.providers.speech.comfyui import ComfyUISpeech
from liberastra.providers.speech.liber_speech import LiberSpeech
from liberastra.providers.tts.edge_tts import EdgeTTS
from liberastra.providers.tts.openai_tts import OpenAITTS


def encrypt_api_key(raw: str) -> str:
    return get_fernet().encrypt(raw.encode("utf-8")).decode("ascii")


def decrypt_api_key(record: Provider) -> str | None:
    if not record.api_key_encrypted:
        return None
    return get_fernet().decrypt(record.api_key_encrypted.encode("ascii")).decode("utf-8")


def build_adapter(
    record: Provider,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float | None = None,
) -> Any:
    """按 Provider 类型构造能力适配器。timeout 仅对 LLM 类生效。"""
    api_key = decrypt_api_key(record)
    default_model = record.extra.get("model") if record.extra else None
    llm_kw: dict[str, Any] = {"client": client}
    if timeout is not None:
        llm_kw["timeout"] = timeout
    if record.type == "ollama":
        return OllamaLLM(record.base_url, **llm_kw)
    if record.type == "openai_compatible":
        return OpenAICompatibleLLM(record.base_url, api_key, **llm_kw)
    if record.type == "openai_tts":
        return OpenAITTS(record.base_url, api_key, default_model or "tts-1", client=client)
    if record.type == "edge_tts":
        return EdgeTTS(default_voice=default_model or "zh-CN-XiaoxiaoNeural")
    if record.type == "openai_stt":
        return OpenAISTT(record.base_url, api_key, default_model or "whisper-1", client=client)
    if record.type == "liber_speech":
        return LiberSpeech(record.base_url, api_key, default_model or "multilingual", client=client)
    if record.type == "comfyui":
        return ComfyUIImage(record.base_url)
    if record.type == "openai_images":
        return OpenAIImages(record.base_url, api_key, default_model or "gpt-image-1", client=client)
    raise ProviderError(f"未知 Provider 类型: {record.type}")


# 兼容旧引用（M1 的 services.llm 使用）
def build_llm_adapter(
    record: Provider,
    *,
    client: httpx.AsyncClient | None = None,
    db: Session | None = None,
    timeout: float | None = None,
) -> Any:
    """构造 LLM 适配器；传入 db 时读取系统设置里的 llm_request_timeout_seconds。"""
    if timeout is None and db is not None:
        from liberastra.services.preferences import get_pref

        timeout = float(get_pref(db, "llm_request_timeout_seconds"))
    return build_adapter(record, client=client, timeout=timeout)


def _speech_default_model(db: Session | None, extra_model: str | None) -> str:
    """系统设置优先，其次 Provider extra.model，最后 multilingual_v3。"""
    if db is not None:
        from liberastra.models import AppSetting

        row = db.get(AppSetting, "default_speech_model")
        if row is not None and str(row.value or "").strip():
            return str(row.value).strip()
    extra = str(extra_model or "").strip()
    return extra or "multilingual_v3"


def build_tts_adapter(
    record: Provider,
    *,
    client: httpx.AsyncClient | None = None,
    db: Session | None = None,
) -> Any:
    """TTS 适配器：comfyui 走语音工作流包；Liber Speech 使用系统默认模型包。"""
    if record.type == "comfyui":
        return ComfyUISpeech(record.base_url)
    if record.type == "liber_speech":
        extra_model = record.extra.get("model") if record.extra else None
        return LiberSpeech(
            record.base_url,
            decrypt_api_key(record),
            _speech_default_model(db, extra_model),
            client=client,
        )
    return build_adapter(record, client=client)


def _speech_default_asr_model(db: Session | None, extra_model: str | None) -> str:
    """系统设置优先。空串表示跟随语音服务 .env。"""
    if db is not None:
        from liberastra.models import AppSetting

        row = db.get(AppSetting, "default_asr_model")
        if row is not None:
            return str(row.value or "").strip()
    return str(extra_model or "").strip()


def build_asr_adapter(
    record: Provider,
    *,
    client: httpx.AsyncClient | None = None,
    db: Session | None = None,
) -> Any:
    if record.type == "liber_speech":
        extra_model = record.extra.get("model") if record.extra else None
        extra_asr = record.extra.get("asr_model") if record.extra else None
        return LiberSpeech(
            record.base_url,
            decrypt_api_key(record),
            _speech_default_model(db, extra_model),
            client=client,
            default_asr_model=_speech_default_asr_model(db, extra_asr),
        )
    return build_adapter(record, client=client)


def build_image_adapter(record: Provider, *, client: httpx.AsyncClient | None = None) -> Any:
    return build_adapter(record, client=client)


async def test_connection(record: Provider) -> str:
    return await build_adapter(record).test()  # type: ignore[no-any-return]


def enabled_liber_speech(db: Session) -> Provider:
    """系统设置读取模型清单时用的 Liber Speech。取第一个启用的。"""
    record = db.scalar(
        select(Provider)
        .where(Provider.enabled.is_(True), Provider.type == "liber_speech")
        .order_by(Provider.id)
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="尚未配置启用的 Liber Speech")
    return record


async def fetch_speech_catalog(record: Provider) -> dict[str, Any]:
    """向 Liber Speech 要 tts_models 和 asr_models。"""
    if record.type != "liber_speech":
        raise ProviderError("只有 Liber Speech 返回合成与识别模型清单")
    adapter = LiberSpeech(record.base_url, decrypt_api_key(record))
    return await adapter.list_catalog()


async def fetch_models(record: Provider) -> list[str]:
    adapter = build_adapter(record)
    if hasattr(adapter, "list_models"):
        return await adapter.list_models()  # type: ignore[no-any-return]
    if hasattr(adapter, "list_voices"):
        return await adapter.list_voices()  # type: ignore[no-any-return]
    raise ProviderError(f"{record.type} 不支持拉取列表")


async def fetch_model_folder(record: Provider, folder: str) -> list[str]:
    """列出某个模型子目录的文件（如 checkpoints / upscale_models），供工作流参数下拉选择。

    特殊形式 ``node:<节点类型>:<字段名>``：从 ComfyUI object_info 读取该节点
    下拉输入（combo）的候选值，例如 tts_edge 音色的 node:EdgeTTS:voice。
    """
    if folder.startswith("node:"):
        parts = folder.split(":", 2)
        if len(parts) != 3:
            raise ProviderError(f"node 选项格式应为 node:<节点类型>:<字段名>，收到 {folder}")
        _, node_type, field_name = parts
        adapter = build_adapter(record)
        client = getattr(adapter, "client", None)
        if client is None or not hasattr(client, "object_info"):
            raise ProviderError(f"{record.type} 不支持读取节点选项")
        info = await client.object_info()
        node = info.get(node_type)
        if node is None:
            raise ProviderError(f"ComfyUI 中没有节点 {node_type}")
        for group in ("required", "optional"):
            spec = node.get("input", {}).get(group, {}).get(field_name)
            # combo 输入的定义形如 [["选项A", "选项B"], {…}] 或 [["A","B"]]
            if isinstance(spec, list) and spec and isinstance(spec[0], list):
                return [str(v) for v in spec[0]]
        raise ProviderError(f"节点 {node_type} 的 {field_name} 不是下拉输入")
    adapter = build_adapter(record)
    if hasattr(adapter, "list_model_folder"):
        return await adapter.list_model_folder(folder)  # type: ignore[no-any-return]
    # edge_tts 等：无子目录概念时，voices / models 走 list_voices / list_models
    if folder in ("voices", "models") and hasattr(adapter, "list_voices"):
        return await adapter.list_voices()  # type: ignore[no-any-return]
    if folder in ("voices", "models") and hasattr(adapter, "list_models"):
        return await adapter.list_models()  # type: ignore[no-any-return]
    raise ProviderError(f"{record.type} 不支持按目录拉取模型")


def pick_provider(db: Session, capability: str, provider_id: int | None = None) -> Provider:
    """按能力挑选 Provider：指定 id 则校验，否则取第一个启用的。"""
    if provider_id is not None:
        record = db.get(Provider, provider_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider 不存在")
        if not record.enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Provider 已停用"
            )
        if capability not in effective_capabilities(record):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"该 Provider 不具备 {capability} 能力",
            )
        return record

    for record in db.scalars(select(Provider).where(Provider.enabled.is_(True))).all():
        if capability in effective_capabilities(record):
            return record
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"尚未配置任何启用的 {capability} Provider",
    )


def pick_llm_with_model(
    db: Session,
    provider_id: int | None = None,
    model: str = "",
) -> tuple[Provider, str]:
    """解析 LLM Provider 与模型名。

    Provider 优先级：请求显式 id → 系统设置 default_llm_provider_id（>0 且仍启用）→ 第一个启用的 llm。
    模型优先级：请求显式 model → 系统设置 default_llm_model → provider.extra.model
    → provider.models[0] → \"default\"。
    """
    from liberastra.services.preferences import get_pref, get_str_pref

    chosen_id = provider_id
    if chosen_id is None:
        pref_id = get_pref(db, "default_llm_provider_id")
        if pref_id > 0:
            record = db.get(Provider, pref_id)
            if (
                record is not None
                and record.enabled
                and "llm" in effective_capabilities(record)
            ):
                chosen_id = pref_id
    provider = pick_provider(db, "llm", chosen_id)

    if model and model.strip():
        resolved = model.strip()
    else:
        pref_model = get_str_pref(db, "default_llm_model").strip()
        if pref_model:
            resolved = pref_model
        else:
            extra_model = (provider.extra or {}).get("model") or ""
            if isinstance(extra_model, str) and extra_model.strip():
                resolved = extra_model.strip()
            elif provider.models:
                resolved = str(provider.models[0])
            else:
                resolved = "default"
    return provider, resolved


def effective_capabilities(record: Provider) -> list[str]:
    """有效能力：以类型注册表为准（存量记录的 capabilities 是创建时快照，可能滞后）。"""
    from liberastra.providers import PROVIDER_TYPES

    info = PROVIDER_TYPES.get(record.type)
    if info is not None:
        return list(info.capabilities)
    return list(record.capabilities or [])


def provider_host(record: Provider) -> str:
    """Provider 的主机组键：base_url 的主机名归一化。

    localhost / 127.0.0.1 / ::1 / 空地址都归一为 "local"。
    同一台显卡主机上的多个 Provider（不同端口、不同服务）会得到同一个组键，
    供串行模式做互斥。
    """
    from urllib.parse import urlparse

    host = (urlparse(record.base_url or "").hostname or "").lower()
    if host in ("", "localhost", "127.0.0.1", "::1"):
        return "local"
    return host
