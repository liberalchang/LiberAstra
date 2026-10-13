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
from liberastra.providers.llm.ollama import OllamaLLM
from liberastra.providers.llm.openai_compatible import OpenAICompatibleLLM
from liberastra.providers.tts.edge_tts import EdgeTTS
from liberastra.providers.tts.openai_tts import OpenAITTS


def encrypt_api_key(raw: str) -> str:
    return get_fernet().encrypt(raw.encode("utf-8")).decode("ascii")


def decrypt_api_key(record: Provider) -> str | None:
    if not record.api_key_encrypted:
        return None
    return get_fernet().decrypt(record.api_key_encrypted.encode("ascii")).decode("utf-8")


def build_adapter(record: Provider, *, client: httpx.AsyncClient | None = None) -> Any:
    """按 Provider 类型构造能力适配器。"""
    api_key = decrypt_api_key(record)
    default_model = record.extra.get("model") if record.extra else None
    if record.type == "ollama":
        return OllamaLLM(record.base_url, client=client)
    if record.type == "openai_compatible":
        return OpenAICompatibleLLM(record.base_url, api_key, client=client)
    if record.type == "openai_tts":
        return OpenAITTS(record.base_url, api_key, default_model or "tts-1", client=client)
    if record.type == "edge_tts":
        return EdgeTTS()
    if record.type == "openai_stt":
        return OpenAISTT(record.base_url, api_key, default_model or "whisper-1", client=client)
    raise ProviderError(f"未知 Provider 类型: {record.type}")


# 兼容旧引用（M1 的 services.llm 使用）
def build_llm_adapter(record: Provider, *, client: httpx.AsyncClient | None = None) -> Any:
    return build_adapter(record, client=client)


def build_tts_adapter(record: Provider, *, client: httpx.AsyncClient | None = None) -> Any:
    return build_adapter(record, client=client)


def build_asr_adapter(record: Provider, *, client: httpx.AsyncClient | None = None) -> Any:
    return build_adapter(record, client=client)


async def test_connection(record: Provider) -> str:
    return await build_adapter(record).test()  # type: ignore[no-any-return]


async def fetch_models(record: Provider) -> list[str]:
    adapter = build_adapter(record)
    if hasattr(adapter, "list_models"):
        return await adapter.list_models()  # type: ignore[no-any-return]
    if hasattr(adapter, "list_voices"):
        return await adapter.list_voices()  # type: ignore[no-any-return]
    raise ProviderError(f"{record.type} 不支持拉取列表")


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
        if capability not in record.capabilities:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"该 Provider 不具备 {capability} 能力",
            )
        return record

    for record in db.scalars(select(Provider).where(Provider.enabled.is_(True))).all():
        if capability in record.capabilities:
            return record
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"尚未配置任何启用的 {capability} Provider",
    )
