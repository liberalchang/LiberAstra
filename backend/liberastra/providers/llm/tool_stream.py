"""OpenAI 兼容流式响应解析：文本增量 + 累积的 tool_calls。

`iter_openai_chat` 产出 `("text", str)` 与最后一帧 `("done", list[dict])`，
工具的 arguments 保持 JSON 字符串，由运行时统一解析。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from liberastra.providers.base import ProviderError
from liberastra.providers.http_errors import http_provider_error


def _merge_tool_delta(
    calls: dict[int, dict[str, Any]], delta: dict[str, Any]
) -> None:
    try:
        index = int(delta.get("index") or 0)
    except (TypeError, ValueError):
        index = 0
    slot = calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
    if delta.get("id"):
        slot["id"] = str(delta["id"])
    function = delta.get("function")
    if isinstance(function, dict):
        if function.get("name"):
            slot["name"] = str(function["name"])
        if function.get("arguments") is not None:
            slot["arguments"] += str(function["arguments"])


def _final_calls(calls: dict[int, dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for index in sorted(calls):
        slot = calls[index]
        if not slot.get("name"):
            continue
        out.append(
            {
                "id": str(slot.get("id") or f"call_{index}"),
                "name": str(slot["name"]),
                "arguments": str(slot.get("arguments") or "{}"),
            }
        )
    return out


async def iter_openai_chat(
    http: httpx.AsyncClient | None,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    *,
    timeout: float = 300.0,
) -> AsyncIterator[tuple[str, Any]]:
    """请求 /chat/completions 并解析 SSE。"""
    own_client = http is None
    client = http or httpx.AsyncClient(timeout=timeout)
    calls: dict[int, dict[str, Any]] = {}
    reasoning: list[str] = []
    try:
        async with client.stream(
            "POST", url, headers=headers, json={**body, "stream": True}
        ) as resp:
            if resp.status_code >= 400:
                err_text = (await resp.aread()).decode("utf-8", errors="replace")[:500]
                raise ProviderError(f"HTTP {resp.status_code}: {err_text}")
            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type:
                data = json.loads((await resp.aread()).decode("utf-8", errors="replace"))
                choices = data.get("choices") if isinstance(data, dict) else None
                message = (
                    choices[0].get("message")
                    if isinstance(choices, list) and choices and isinstance(choices[0], dict)
                    else {}
                )
                text = message.get("content") if isinstance(message, dict) else None
                if text:
                    yield ("text", str(text))
                thought = (
                    message.get("reasoning_content") or message.get("reasoning")
                    if isinstance(message, dict)
                    else None
                )
                if thought:
                    yield ("reasoning", str(thought))
                for item in (message.get("tool_calls") if isinstance(message, dict) else None) or []:
                    if not isinstance(item, dict):
                        continue
                    function = item.get("function") or {}
                    calls[len(calls)] = {
                        "id": str(item.get("id") or ""),
                        "name": str(function.get("name") or ""),
                        "arguments": str(function.get("arguments") or "{}"),
                    }
                yield ("done", _final_calls(calls))
                return
            async for line in resp.aiter_lines():
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload:
                    continue
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") if isinstance(chunk, dict) else None
                if not isinstance(choices, list) or not choices:
                    continue
                delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
                if not isinstance(delta, dict):
                    continue
                content = delta.get("content")
                if content:
                    yield ("text", str(content))
                thought = delta.get("reasoning_content") or delta.get("reasoning")
                if thought:
                    reasoning.append(str(thought))
                for tool_delta in delta.get("tool_calls") or []:
                    if isinstance(tool_delta, dict):
                        _merge_tool_delta(calls, tool_delta)
    except ProviderError:
        raise
    except httpx.HTTPError as exc:
        raise http_provider_error(url, timeout, exc) from exc
    finally:
        if own_client:
            await client.aclose()
    if reasoning:
        yield ("reasoning", "".join(reasoning))
    yield ("done", _final_calls(calls))
