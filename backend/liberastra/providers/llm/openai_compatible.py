"""OpenAI 兼容 LLM 适配器：覆盖 vLLM / LM Studio / DeepSeek / SiliconFlow 等。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from liberastra.providers.base import ProviderError


async def _json_request(
    client: httpx.AsyncClient | None,
    timeout: float,
    method: str,
    url: str,
    headers: dict[str, str],
    **kwargs: Any,
) -> Any:
    own_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout)
    try:
        resp = await http.request(method, url, headers=headers, **kwargs)
        if resp.status_code >= 400:
            raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        return resp.json()
    except httpx.TimeoutException as exc:
        raise ProviderError(f"请求超时 {url}（>{timeout:.0f}s）: {exc}") from exc
    except httpx.HTTPError as exc:
        raise ProviderError(f"无法连接 {url}: {exc}") from exc
    finally:
        if own_client:
            await http.aclose()


def _delta_text(chunk: dict[str, Any]) -> str:
    """从 OpenAI 流式 chunk 抽出增量文本。"""
    try:
        delta = chunk["choices"][0].get("delta") or {}
        content = delta.get("content")
        return str(content) if content else ""
    except (KeyError, IndexError, TypeError, AttributeError):
        return ""


class OpenAICompatibleLLM:
    """标准 /v1/chat/completions + /v1/models。"""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 300.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = client
        self._timeout = timeout
        self._extra_headers = dict(extra_headers or {})

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self._extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat(self, *, model: str, messages: list[dict[str, Any]], **params: Any) -> str:
        data = await _json_request(
            self._client,
            self._timeout,
            "POST",
            f"{self.base_url}/chat/completions",
            self._headers(),
            json={"model": model, "messages": messages, **params},
        )
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"响应格式异常: {str(data)[:500]}") from exc

    async def chat_stream(
        self, *, model: str, messages: list[dict[str, Any]], **params: Any
    ) -> AsyncIterator[str]:
        """流式 chat：逐段 yield 增量文本（Ollama /v1 与多数 OpenAI 兼容服务均支持）。"""
        own_client = self._client is None
        http = self._client or httpx.AsyncClient(timeout=self._timeout)
        url = f"{self.base_url}/chat/completions"
        body = {"model": model, "messages": messages, "stream": True, **params}
        try:
            async with http.stream(
                "POST", url, headers=self._headers(), json=body
            ) as resp:
                if resp.status_code >= 400:
                    err_text = (await resp.aread()).decode("utf-8", errors="replace")[:500]
                    raise ProviderError(f"HTTP {resp.status_code}: {err_text}")
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith(":"):
                        continue  # SSE 注释 / keep-alive
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        if payload == "[DONE]":
                            break
                        continue
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    text = _delta_text(chunk)
                    if text:
                        yield text
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError(f"请求超时 {url}（>{self._timeout:.0f}s）: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"无法连接 {url}: {exc}") from exc
        finally:
            if own_client:
                await http.aclose()

    async def list_models(self) -> list[str]:
        data = await _json_request(
            self._client, self._timeout, "GET", f"{self.base_url}/models", self._headers()
        )
        return sorted(m["id"] for m in data.get("data", []) if "id" in m)

    async def test(self) -> str:
        models = await self.list_models()
        return f"连接成功，可用模型 {len(models)} 个"
