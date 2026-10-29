"""官方云端对话供应商：注册表、预设、OpenAI 兼容路由、Anthropic Messages。"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from liberastra.providers import PROVIDER_TYPES
from liberastra.providers.llm.openai_compatible import OpenAICompatibleLLM
from liberastra.providers.vendors.cloud.anthropic import ANTHROPIC_VERSION, AnthropicLLM
from liberastra.providers.vendors.volcengine.presets import presets_for
from liberastra.services.providers import build_adapter

CLOUD = {
    "anthropic": "https://api.anthropic.com",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openai": "https://api.openai.com/v1",
    "chatgpt": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "kimi_code": "https://api.kimi.com/coding/v1",
    "aliyun_bailian": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}


def _record(provider_type: str, base_url: str) -> SimpleNamespace:
    return SimpleNamespace(type=provider_type, base_url=base_url, api_key_encrypted=None, extra={})


def test_cloud_types_registered() -> None:
    for provider_type, base in CLOUD.items():
        info = PROVIDER_TYPES[provider_type]
        assert info.default_base_url == base
        assert info.capabilities == ("llm",)
        assert info.requires_api_key is False
        assert presets_for(provider_type)


def test_volcengine_presets_still_resolve() -> None:
    ids = {item["id"] for item in presets_for("volcengine_ark")}
    assert "doubao-seed-1-6-251015" in ids


def test_build_adapter_routes_cloud_llms() -> None:
    deepseek = build_adapter(_record("deepseek", CLOUD["deepseek"]))
    assert isinstance(deepseek, OpenAICompatibleLLM)
    assert deepseek.base_url == CLOUD["deepseek"]
    google = build_adapter(_record("google", CLOUD["google"]))
    assert isinstance(google, OpenAICompatibleLLM)
    assert google._extra_headers["x-goog-api-client"] == "liberastra/1.0"
    assert isinstance(build_adapter(_record("anthropic", CLOUD["anthropic"])), AnthropicLLM)
    assert isinstance(build_adapter(_record("chatgpt", CLOUD["chatgpt"])), OpenAICompatibleLLM)


def test_capabilities_include_cloud_cards(client: TestClient, auth_header: dict[str, str]) -> None:
    data = client.get("/api/v1/capabilities", headers=auth_header).json()
    types = {item["type"]: item for item in data["provider_types"]}
    assert set(CLOUD) <= set(types)
    assert types["kimi_code"]["default_base_url"] == CLOUD["kimi_code"]
    assert types["aliyun_bailian"]["label"] == "阿里云百炼"


def test_create_deepseek_seeds_enabled_preset(client: TestClient, auth_header: dict[str, str]) -> None:
    created = client.post(
        "/api/v1/providers",
        json={"name": "DeepSeek", "type": "deepseek"},
        headers=auth_header,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["base_url"] == CLOUD["deepseek"]
    assert body["models"] == ["deepseek-chat"]


def test_anthropic_lifts_system_and_pages_models() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/messages":
            seen["headers"] = dict(request.headers)
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"content": [{"type": "text", "text": "你好"}]})
        if request.url.path == "/v1/models":
            if request.url.params.get("after_id"):
                return httpx.Response(200, json={"data": [{"id": "b"}], "has_more": False, "last_id": "b"})
            return httpx.Response(200, json={"data": [{"id": "a"}], "has_more": True, "last_id": "a"})
        return httpx.Response(404)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            adapter = AnthropicLLM("https://api.anthropic.com", "sk-ant", client=http)
            text = await adapter.chat(
                model="claude-sonnet-4-6",
                messages=[
                    {"role": "system", "content": "你是助手"},
                    {"role": "user", "content": "hi"},
                ],
            )
            assert text == "你好"
            assert await adapter.list_models() == ["a", "b"]

    asyncio.run(run())
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["system"] == "你是助手"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert body["max_tokens"] == 4096
    headers = {key.lower(): value for key, value in seen["headers"].items()}  # type: ignore[union-attr]
    assert headers["x-api-key"] == "sk-ant"
    assert headers["anthropic-version"] == ANTHROPIC_VERSION


def test_google_compat_sends_client_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-client"] == "liberastra/1.0"
        assert request.url.path == "/v1beta/openai/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            adapter = build_adapter(_record("google", CLOUD["google"]), client=http)
            text = await adapter.chat(
                model="gemini-2.5-flash",
                messages=[{"role": "user", "content": "hi"}],
            )
            assert text == "ok"

    asyncio.run(run())
