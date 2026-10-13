"""OpenAI 兼容 TTS 适配器：标准 /v1/audio/speech。

覆盖 OpenAI、SiliconFlow、Kokoro-FastAPI、Speaches 等兼容服务。
"""

from __future__ import annotations

from typing import Any

import httpx

from liberastra.providers.base import ProviderError
from liberastra.providers.llm.openai_compatible import _json_request

# OpenAI 标准格式别名：ogg_opus 在 OpenAI 兼容层里通常叫 opus
_FORMAT_ALIASES = {"ogg_opus": "opus"}


class OpenAITTS:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        default_model: str = "tts-1",
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self._client = client
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def synthesize(
        self,
        *,
        text: str,
        voice: str,
        model: str | None = None,
        fmt: str = "mp3",
        **params: Any,
    ) -> bytes:
        own_client = self._client is None
        http = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            resp = await http.post(
                f"{self.base_url}/audio/speech",
                headers=self._headers(),
                json={
                    "model": model or self.default_model,
                    "input": text,
                    "voice": voice,
                    "response_format": _FORMAT_ALIASES.get(fmt, fmt),
                    **params,
                },
            )
            if resp.status_code >= 400:
                raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            return resp.content
        except httpx.HTTPError as exc:
            raise ProviderError(f"无法连接 {self.base_url}: {exc}") from exc
        finally:
            if own_client:
                await http.aclose()

    async def list_voices(self) -> list[str]:
        """Kokoro-FastAPI 等提供 /audio/voices；不支持的返回空列表。"""
        try:
            data = await _json_request(
                self._client, self._timeout, "GET", f"{self.base_url}/audio/voices", self._headers()
            )
        except ProviderError:
            return []
        voices = data.get("voices", data if isinstance(data, list) else [])
        return [str(v) for v in voices]

    async def test(self) -> str:
        try:
            voices = await self.list_voices()
        except ProviderError:
            voices = []
        if voices:
            return f"连接成功，可用音色 {len(voices)} 个"
        # 没有 voices 端点的服务退化为 /models 探活
        data = await _json_request(
            self._client, self._timeout, "GET", f"{self.base_url}/models", self._headers()
        )
        return f"连接成功，可用模型 {len(data.get('data', []))} 个"
