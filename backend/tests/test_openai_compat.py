"""OpenAI 兼容 /v1/chat/completions 与 /v1/images/generations 测试。"""

import pytest
from fastapi.testclient import TestClient


class _FakeLLM:
    async def chat(self, *, model: str, messages: list, **kwargs) -> str:
        return "你好，我是助手"


class _FakeImage:
    async def generate(self, **kwargs) -> list[tuple[str, bytes]]:
        return [("a.png", b"PNG-BYTES")]


@pytest.fixture()
def llm_and_image_providers(client: TestClient, auth_header: dict[str, str]) -> None:
    for name, ptype in (("llm", "openai_compatible"), ("img", "openai_images")):
        resp = client.post(
            "/api/v1/providers",
            json={"name": name, "type": ptype, "base_url": "http://mock/v1"},
            headers=auth_header,
        )
        assert resp.status_code == 201


def test_chat_completions(
    client: TestClient,
    auth_header: dict[str, str],
    llm_and_image_providers: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from liberastra.api.routes import openai_compat

    monkeypatch.setattr(openai_compat, "build_llm_adapter", lambda record, **_kw: _FakeLLM())

    resp = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-x", "messages": [{"role": "user", "content": "hi"}]},
        headers=auth_header,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "你好，我是助手"
    assert body["choices"][0]["finish_reason"] == "stop"


def test_chat_completions_stream_rejected(
    client: TestClient, auth_header: dict[str, str], llm_and_image_providers: None
) -> None:
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
        headers=auth_header,
    )
    assert resp.status_code == 400


def test_images_generations(
    client: TestClient,
    auth_header: dict[str, str],
    llm_and_image_providers: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from liberastra.api.routes import openai_compat

    monkeypatch.setattr(openai_compat, "build_image_adapter", lambda record: _FakeImage())

    resp = client.post(
        "/v1/images/generations",
        json={"prompt": "一只猫", "n": 1, "response_format": "b64_json"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    import base64

    assert base64.b64decode(resp.json()["data"][0]["b64_json"]) == b"PNG-BYTES"
