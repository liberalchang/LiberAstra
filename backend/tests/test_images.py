"""图像任务、OpenAI 图像适配器与提示词优化集成测试。"""

import asyncio
import base64

import httpx
import pytest
from fastapi.testclient import TestClient

from liberastra.providers.image.openai_images import OpenAIImages


@pytest.fixture()
def comfy_provider(client: TestClient, auth_header: dict[str, str]) -> int:
    resp = client.post(
        "/api/v1/providers",
        json={"name": "mock-comfy", "type": "comfyui", "base_url": "http://mock:8188"},
        headers=auth_header,
    )
    assert resp.status_code == 201
    return resp.json()["id"]  # noqa: RET504


class _FakeImage:
    async def generate(self, **kwargs) -> list[tuple[str, bytes]]:
        await asyncio.sleep(0)
        return [("a.png", b"PNG-A"), ("b.png", b"PNG-B")]


def test_image_generate_job(
    client: TestClient,
    auth_header: dict[str, str],
    comfy_provider: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from liberastra.services import image as image_service

    monkeypatch.setattr(image_service, "build_image_adapter", lambda record: _FakeImage())

    resp = client.post(
        "/api/v1/images/generate?wait=true",
        json={
            "provider_id": comfy_provider,
            "workflow": "t2i_basic",
            "prompt": "一只猫",
            "inputs": {"ckpt_name": "m.safetensors"},
        },
        headers=auth_header,
    )
    assert resp.status_code == 202
    job = resp.json()
    assert job["status"] == "succeeded", job["error"]
    assert len(job["outputs"]) == 2

    content = client.get(f"/api/v1/assets/{job['outputs'][0]['asset_id']}/content", headers=auth_header)
    assert content.content == b"PNG-A"


def test_image_generate_requires_workflow_for_comfy(
    client: TestClient, auth_header: dict[str, str], comfy_provider: int
) -> None:
    resp = client.post(
        "/api/v1/images/generate",
        json={"provider_id": comfy_provider, "prompt": "猫"},
        headers=auth_header,
    )
    assert resp.status_code == 400


def test_openai_images_adapter() -> None:
    png_b64 = base64.b64encode(b"PNG-DATA").decode()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/images/generations":
            return httpx.Response(200, json={"data": [{"b64_json": png_b64}]})
        if request.url.path == "/v1/images/edits":
            return httpx.Response(200, json={"data": [{"b64_json": png_b64}]})
        return httpx.Response(404)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            adapter = OpenAIImages("http://mock/v1", "k", client=http)
            images = await adapter.generate(prompt="猫", size="1024x1024")
            assert images == [("image_0.png", b"PNG-DATA")]
            edited = await adapter.edit(image=("in.png", b"in"), prompt="变狗")
            assert edited[0][1] == b"PNG-DATA"

    asyncio.run(run())


def test_optimize_prompt(
    client: TestClient,
    auth_header: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from liberastra.services import image as image_service

    class _FakeLLM:
        async def chat(self, **kwargs) -> str:
            return "杰作，一只橘猫，逆光，浅景深，8k"

    monkeypatch.setattr(image_service, "build_llm_adapter", lambda record: _FakeLLM())

    llm = client.post(
        "/api/v1/providers",
        json={"name": "llm", "type": "openai_compatible", "base_url": "http://mock/v1"},
        headers=auth_header,
    ).json()
    resp = client.post(
        "/api/v1/images/optimize-prompt",
        json={"provider_id": llm["id"], "prompt": "一只猫"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert "橘猫" in resp.json()["optimized"]


def test_workflows_api(client: TestClient, auth_header: dict[str, str]) -> None:
    packs = client.get("/api/v1/workflows", headers=auth_header).json()
    assert any(p["name"] == "t2i_basic" and p["source"] == "builtin" for p in packs)

    created = client.post(
        "/api/v1/workflows/import",
        json={
            "name": "ui_pack",
            "capability": "t2i",
            "workflow": {"1": {"class_type": "N", "inputs": {"text": ""}}},
            "inputs": {"prompt": {"node": "1", "field": "inputs.text", "type": "str"}},
        },
        headers=auth_header,
    )
    assert created.status_code == 201
    assert client.delete("/api/v1/workflows/ui_pack", headers=auth_header).status_code == 204
