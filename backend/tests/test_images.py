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

    asset = client.get(f"/api/v1/assets/{job['outputs'][0]['asset_id']}", headers=auth_header).json()
    assert asset["meta"]["prompt"] == "一只猫"
    assert asset["meta"]["workflow"] == "t2i_basic"
    assert asset["meta"]["provider"] == "mock-comfy"
    assert asset["meta"]["source_name"] == "a.png"
    assert asset["meta"]["duration_s"] >= 0

    content = client.get(f"/api/v1/assets/{job['outputs'][0]['asset_id']}/content", headers=auth_header)
    assert content.content == b"PNG-A"
    # 下载文件名携带日期 + 提示词摘要（非 ASCII 经 RFC 5987 编码）
    disposition = content.headers["content-disposition"]
    assert "image_0.png" not in disposition
    assert ".png" in disposition


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
    from liberastra.services import prompts as prompt_service

    class _FakeLLM:
        async def chat(self, **kwargs) -> str:
            return "杰作，一只橘猫，逆光，浅景深，8k"

    monkeypatch.setattr(prompt_service, "build_llm_adapter", lambda record, **_kw: _FakeLLM())

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

    # 新路径：提交 Job；wait=true 同步等到终态
    resp2 = client.post(
        "/api/v1/prompts/optimize?wait=true",
        json={"provider_id": llm["id"], "prompt": "一只猫", "task": "t2i"},
        headers=auth_header,
    )
    assert resp2.status_code == 202, resp2.text
    body2 = resp2.json()
    assert body2["kind"] == "prompt.optimize"
    assert body2["status"] == "succeeded"
    assert "橘猫" in (body2["outputs"][0].get("content") or "")
    assert body2["outputs"][0].get("provider_name")

    # 异步提交同样 202，尚未必终态
    resp3 = client.post(
        "/api/v1/prompts/optimize",
        json={"provider_id": llm["id"], "prompt": "一只猫", "task": "t2i"},
        headers=auth_header,
    )
    assert resp3.status_code == 202
    assert resp3.json()["id"]
    assert resp3.json()["kind"] == "prompt.optimize"


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
