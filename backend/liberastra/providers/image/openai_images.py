"""OpenAI 兼容图像适配器：/v1/images/generations + /v1/images/edits。

覆盖 OpenAI gpt-image 及各类兼容网关（BananaRouter 类）。
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from liberastra.providers.base import ProviderError
from liberastra.providers.llm.openai_compatible import _json_request


class OpenAIImages:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        default_model: str = "gpt-image-1",
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 300.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self._client = client
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    async def _decode_images(self, data: dict) -> list[tuple[str, bytes]]:
        images: list[tuple[str, bytes]] = []
        for i, item in enumerate(data.get("data", [])):
            if item.get("b64_json"):
                images.append((f"image_{i}.png", base64.b64decode(item["b64_json"])))
            elif item.get("url"):
                own = self._client is None
                http = self._client or httpx.AsyncClient(timeout=self._timeout)
                try:
                    resp = await http.get(item["url"])
                    resp.raise_for_status()
                    images.append((f"image_{i}.png", resp.content))
                finally:
                    if own:
                        await http.aclose()
        if not images:
            raise ProviderError(f"图像服务未返回图片: {str(data)[:300]}")
        return images

    async def generate(
        self,
        *,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
        model: str | None = None,
        **params: Any,
    ) -> list[tuple[str, bytes]]:
        data = await _json_request(
            self._client,
            self._timeout,
            "POST",
            f"{self.base_url}/images/generations",
            {**self._headers(), "Content-Type": "application/json"},
            json={"model": model or self.default_model, "prompt": prompt, "size": size, "n": n, **params},
        )
        return await self._decode_images(data)

    async def edit(
        self,
        *,
        image: tuple[str, bytes],
        prompt: str,
        size: str = "1024x1024",
        model: str | None = None,
        **params: Any,
    ) -> list[tuple[str, bytes]]:
        own = self._client is None
        http = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            resp = await http.post(
                f"{self.base_url}/images/edits",
                headers=self._headers(),
                data={"model": model or self.default_model, "prompt": prompt, "size": size, **params},
                files={"image": image},
            )
            if resp.status_code >= 400:
                raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            return await self._decode_images(resp.json())
        except httpx.HTTPError as exc:
            raise ProviderError(f"无法连接 {self.base_url}: {exc}") from exc
        finally:
            if own:
                await http.aclose()

    async def test(self) -> str:
        data = await _json_request(
            self._client, self._timeout, "GET", f"{self.base_url}/models", self._headers()
        )
        return f"连接成功，可用模型 {len(data.get('data', []))} 个"
