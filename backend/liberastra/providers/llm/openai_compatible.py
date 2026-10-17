"""OpenAI 兼容 LLM 适配器：覆盖 vLLM / LM Studio / DeepSeek / SiliconFlow 等。"""

from __future__ import annotations

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


class OpenAICompatibleLLM:
    """标准 /v1/chat/completions + /v1/models。"""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 300.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = client
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
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

    async def list_models(self) -> list[str]:
        data = await _json_request(
            self._client, self._timeout, "GET", f"{self.base_url}/models", self._headers()
        )
        return sorted(m["id"] for m in data.get("data", []) if "id" in m)

    async def test(self) -> str:
        models = await self.list_models()
        return f"连接成功，可用模型 {len(models)} 个"
