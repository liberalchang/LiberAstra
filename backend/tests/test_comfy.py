"""ComfyClient 与 ComfyUI 图像适配器测试（httpx MockTransport，轮询路径）。"""

import asyncio

import httpx

from liberastra.providers.base import ProviderError
from liberastra.providers.comfyui.client import ComfyClient
from liberastra.providers.image.comfyui import ComfyUIImage
from liberastra.services.workflows import get_pack


def _mock_comfy() -> httpx.MockTransport:
    state = {"history_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/system_stats":
            return httpx.Response(200, json={"system": {"comfyui_version": "0.3.0"}})
        if path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "pid-123"})
        if path == "/upload/image":
            return httpx.Response(200, json={"name": "uploaded.png", "subfolder": "", "type": "input"})
        if path.startswith("/history/"):
            state["history_calls"] += 1
            if state["history_calls"] < 2:
                return httpx.Response(200, json={})
            return httpx.Response(
                200,
                json={
                    "pid-123": {
                        "status": {"status_str": "success", "completed": True},
                        "outputs": {
                            "9": {
                                "images": [
                                    {"filename": "out.png", "subfolder": "", "type": "output"}
                                ]
                            }
                        },
                    }
                },
            )
        if path == "/view":
            return httpx.Response(200, content=b"PNG-BYTES")
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_comfy_lists_model_folders() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/models/checkpoints":
            return httpx.Response(200, json=[])
        if path == "/models/diffusion_models":
            return httpx.Response(200, json=["qwen.safetensors"])
        if path == "/models/vae":
            return httpx.Response(200, json=["vae.safetensors"])
        return httpx.Response(404, text=path)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = ComfyClient("http://comfy:8188", client=http)
            names = await client.list_model_files()
            assert names == ["diffusion_models/qwen.safetensors", "vae/vae.safetensors"]

    asyncio.run(run())


def test_comfy_client_flow() -> None:
    async def run() -> None:
        async with httpx.AsyncClient(transport=_mock_comfy()) as http:
            client = ComfyClient("http://comfy:8188", client=http)
            assert "0.3.0" in await client.test()

            prompt_id = await client.queue_prompt({"1": {"class_type": "X", "inputs": {}}})
            assert prompt_id == "pid-123"

            progress: list[float] = []
            result = await client.wait_result(prompt_id, on_progress=progress.append, use_ws=False)
            assert "outputs" in result
            assert progress  # 轮询估计进度有上报

            assert await client.download("out.png") == b"PNG-BYTES"
            name = await client.upload_image("in.png", b"img")
            assert name == "uploaded.png"

            limited = ComfyClient("http://comfy:8188", client=http, upload_limit=3)
            try:
                await limited.upload_image("big.mp4", b"1234")
                raise AssertionError("超限上传应在请求前被拒绝")
            except ProviderError as exc:
                assert "已拒绝上传" in str(exc)

    asyncio.run(run())


def test_comfy_history_timeout_retries_while_polling() -> None:
    """本地长任务时 Comfy 忙会导致 /history ReadTimeout；轮询应继续而非整任务失败。"""
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/history/"):
            state["n"] += 1
            if state["n"] == 1:
                raise httpx.ReadTimeout("timed out", request=request)
            return httpx.Response(
                200,
                json={
                    "pid-timeout": {
                        "status": {"status_str": "success", "completed": True},
                        "outputs": {},
                    }
                },
            )
        return httpx.Response(404)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = ComfyClient("http://comfy:8188", client=http)
            result = await client.wait_result("pid-timeout", use_ws=False, timeout=30.0)
            assert result["status"]["status_str"] == "success"
            assert state["n"] >= 2

    asyncio.run(run())


def test_comfy_image_adapter_generate() -> None:
    async def run() -> None:
        async with httpx.AsyncClient(transport=_mock_comfy()) as http:
            adapter = ComfyUIImage("http://comfy:8188", client=ComfyClient("http://comfy:8188", client=http))
            pack = get_pack("t2i_basic")
            images = await adapter.generate(
                pack=pack,
                inputs={"prompt": "一只猫", "ckpt_name": "m.safetensors"},
                use_ws=False,
            )
            assert images == [("out.png", b"PNG-BYTES")]

    asyncio.run(run())
