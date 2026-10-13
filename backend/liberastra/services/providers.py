"""Provider 服务：密钥加解密、适配器构造、连接测试、模型拉取。"""

from __future__ import annotations

import httpx

from liberastra.core.security import get_fernet
from liberastra.models import Provider
from liberastra.providers.base import LLMAdapter, ProviderError
from liberastra.providers.llm.ollama import OllamaLLM
from liberastra.providers.llm.openai_compatible import OpenAICompatibleLLM


def encrypt_api_key(raw: str) -> str:
    return get_fernet().encrypt(raw.encode("utf-8")).decode("ascii")


def decrypt_api_key(record: Provider) -> str | None:
    if not record.api_key_encrypted:
        return None
    return get_fernet().decrypt(record.api_key_encrypted.encode("ascii")).decode("utf-8")


def build_llm_adapter(record: Provider, *, client: httpx.AsyncClient | None = None) -> LLMAdapter:
    if record.type == "ollama":
        return OllamaLLM(record.base_url, client=client)
    if record.type == "openai_compatible":
        return OpenAICompatibleLLM(record.base_url, decrypt_api_key(record), client=client)
    raise ProviderError(f"未知 Provider 类型: {record.type}")


async def test_connection(record: Provider) -> str:
    return await build_llm_adapter(record).test()


async def fetch_models(record: Provider) -> list[str]:
    return await build_llm_adapter(record).list_models()
