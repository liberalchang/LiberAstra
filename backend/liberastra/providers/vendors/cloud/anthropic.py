"""Anthropic Messages API。官方文档：https://platform.claude.com/docs/en/api/messages"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from liberastra.providers.base import ProviderError
from liberastra.providers.llm.openai_compatible import _json_request

# Messages API 长期接受的日期版本。控制台新示例可能更新，这个版本仍然有效。
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicLLM:
    """POST /v1/messages，GET /v1/models。密钥放在 Authorization 和 x-api-key。"""

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
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": ANTHROPIC_VERSION,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["x-api-key"] = self.api_key
        return headers

    def _body(self, *, model: str, messages: list[dict[str, Any]], params: dict[str, Any]) -> dict[str, Any]:
        system_parts: list[str] = []
        dialog: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role") or "user")
            content = message.get("content")
            if role == "system":
                if isinstance(content, str) and content.strip():
                    system_parts.append(content)
                continue
            if role not in {"user", "assistant"}:
                role = "user"
            dialog.append({"role": role, "content": content if content is not None else ""})
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": int(params.pop("max_tokens", 4096)),
            "messages": dialog,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        params.pop("stream", None)
        body.update(params)
        return body

    async def chat(self, *, model: str, messages: list[dict[str, Any]], **params: Any) -> str:
        data = await _json_request(
            self._client,
            self._timeout,
            "POST",
            f"{self.base_url}/v1/messages",
            self._headers(),
            json=self._body(model=model, messages=messages, params=dict(params)),
        )
        blocks = data.get("content") if isinstance(data, dict) else None
        if not isinstance(blocks, list):
            raise ProviderError(f"响应格式异常: {str(data)[:500]}")
        text = "".join(
            str(block.get("text") or "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        )
        if not text and blocks:
            raise ProviderError(f"响应里没有文本: {str(data)[:500]}")
        return text

    async def chat_stream(
        self, *, model: str, messages: list[dict[str, Any]], **params: Any
    ) -> AsyncIterator[str]:
        own_client = self._client is None
        http = self._client or httpx.AsyncClient(timeout=self._timeout)
        url = f"{self.base_url}/v1/messages"
        body = self._body(model=model, messages=messages, params=dict(params))
        body["stream"] = True
        try:
            async with http.stream("POST", url, headers=self._headers(), json=body) as resp:
                if resp.status_code >= 400:
                    err_text = (await resp.aread()).decode("utf-8", errors="replace")[:500]
                    raise ProviderError(f"HTTP {resp.status_code}: {err_text}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("delta") if isinstance(chunk, dict) else None
                    if isinstance(delta, dict) and delta.get("type") == "text_delta":
                        text = str(delta.get("text") or "")
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
        ids: list[str] = []
        after: str | None = None
        for _ in range(5):
            url = f"{self.base_url}/v1/models?limit=100"
            if after:
                url = f"{url}&after_id={after}"
            data = await _json_request(self._client, self._timeout, "GET", url, self._headers())
            rows = data.get("data") if isinstance(data, dict) else None
            if not isinstance(rows, list):
                break
            for row in rows:
                if isinstance(row, dict) and row.get("id"):
                    ids.append(str(row["id"]))
            if not data.get("has_more"):
                break
            after = str(data.get("last_id") or "")
            if not after:
                break
        return ids

    async def test(self) -> str:
        models = await self.list_models()
        return f"连接成功，可用模型 {len(models)} 个"
