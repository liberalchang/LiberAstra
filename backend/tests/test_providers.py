"""Provider 注册表、密钥加密、适配器（MockTransport）与管理 API 测试。"""

import asyncio

import httpx
from fastapi.testclient import TestClient

from liberastra.core.db import SessionLocal
from liberastra.models import Provider
from liberastra.providers.llm.ollama import OllamaLLM
from liberastra.providers.llm.openai_compatible import OpenAICompatibleLLM
from liberastra.services.providers import decrypt_api_key


def test_capabilities(client: TestClient, auth_header: dict[str, str]) -> None:
    data = client.get("/api/v1/capabilities", headers=auth_header).json()
    types = {t["type"] for t in data["provider_types"]}
    assert {"openai_compatible", "ollama"} <= types
    assert "llm" in data["capabilities"]


def test_provider_crud_and_encryption(client: TestClient, auth_header: dict[str, str]) -> None:
    created = client.post(
        "/api/v1/providers",
        json={
            "name": "本地 vLLM",
            "type": "openai_compatible",
            "base_url": "http://mock:8000/v1",
            "api_key": "sk-secret-123",
        },
        headers=auth_header,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["has_api_key"] is True
    assert "sk-secret-123" not in str(body)

    db = SessionLocal()
    try:
        record = db.get(Provider, body["id"])
        assert record is not None
        assert record.api_key_encrypted != "sk-secret-123"
        assert decrypt_api_key(record) == "sk-secret-123"
    finally:
        db.close()

    patched = client.patch(
        f"/api/v1/providers/{body['id']}", json={"enabled": False}, headers=auth_header
    )
    assert patched.json()["enabled"] is False

    listing = client.get("/api/v1/providers", headers=auth_header).json()
    assert any(p["id"] == body["id"] for p in listing)

    assert client.delete(f"/api/v1/providers/{body['id']}", headers=auth_header).status_code == 204
    assert (
        client.post(f"/api/v1/providers/{body['id']}/test", headers=auth_header).status_code == 404
    )


def test_openai_compatible_adapter() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer k"
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "m1"}, {"id": "m2"}]})
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(
                200, json={"choices": [{"message": {"role": "assistant", "content": "你好"}}]}
            )
        return httpx.Response(404)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = OpenAICompatibleLLM("http://mock/v1", "k", client=client)
            assert await adapter.list_models() == ["m1", "m2"]
            text = await adapter.chat(model="m1", messages=[{"role": "user", "content": "hi"}])
            assert text == "你好"

    asyncio.run(run())


def test_ollama_adapter_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:8b"}]})
        return httpx.Response(404)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = OllamaLLM("http://mock:11434", client=client)
            assert await adapter.list_models() == ["qwen3:8b"]
            assert "1 个" in await adapter.test()

    asyncio.run(run())
