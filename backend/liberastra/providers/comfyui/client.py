"""自研 ComfyUI 客户端（不依赖 comfykit）。

- POST /prompt 提交工作流；/ws 实时进度，/history/{id} 轮询兜底
- /upload/image 上传输入；/view 下载结果
- /object_info、/models、/system_stats 用于发现与健康检查；/interrupt 中断
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from liberastra.providers.base import ProviderError

ProgressCallback = Callable[[float], None]


class ComfyClient:
    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
        self._client = client
        self._timeout = timeout

    # ---- HTTP 基础 ----

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        own = self._client is None
        http = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            resp = await http.request(method, f"{self.base_url}{path}", **kwargs)
            if resp.status_code >= 400:
                raise ProviderError(f"ComfyUI HTTP {resp.status_code}: {resp.text[:500]}")
            if resp.headers.get("content-type", "").startswith("application/json"):
                return resp.json()
            return resp.content
        except httpx.HTTPError as exc:
            raise ProviderError(f"无法连接 ComfyUI {self.base_url}: {exc}") from exc
        finally:
            if own:
                await http.aclose()

    async def test(self) -> str:
        stats = await self._request("GET", "/system_stats")
        version = stats.get("system", {}).get("comfyui_version", "未知版本")
        return f"ComfyUI 连接成功（{version}）"

    async def object_info(self) -> dict:
        return await self._request("GET", "/object_info")  # type: ignore[no-any-return]

    async def list_checkpoints(self) -> list[str]:
        try:
            return await self._request("GET", "/models/checkpoints")  # type: ignore[no-any-return]
        except ProviderError:
            return []

    async def list_model_files(self) -> list[str]:
        """按目录列出模型文件。checkpoints 为空时仍返回 diffusion_models 等。"""
        folders = (
            "checkpoints",
            "diffusion_models",
            "unet",
            "text_encoders",
            "clip",
            "vae",
            "loras",
            "controlnet",
            "upscale_models",
        )
        names: list[str] = []
        failures = 0
        for folder in folders:
            try:
                files = await self._request("GET", f"/models/{folder}")
            except ProviderError:
                failures += 1
                continue
            if isinstance(files, list):
                names.extend(f"{folder}/{item}" for item in files if isinstance(item, str))
        if not names and failures == len(folders):
            raise ProviderError(f"无法读取 ComfyUI 模型目录 {self.base_url}")
        return names

    async def queue_info(self) -> dict:
        return await self._request("GET", "/queue")  # type: ignore[no-any-return]

    async def interrupt(self) -> None:
        await self._request("POST", "/interrupt")

    # ---- 任务 ----

    async def queue_prompt(self, workflow: dict) -> str:
        data = await self._request("POST", "/prompt", json={"prompt": workflow})
        if "prompt_id" not in data:
            raise ProviderError(f"ComfyUI 拒绝工作流: {str(data)[:500]}")
        return str(data["prompt_id"])

    async def upload_image(self, filename: str, content: bytes, *, overwrite: bool = True) -> str:
        data = await self._request(
            "POST",
            "/upload/image",
            files={"image": (Path(filename).name, content)},
            data={"overwrite": "true" if overwrite else "false"},
        )
        name = data.get("name")
        if not name:
            raise ProviderError(f"上传失败: {str(data)[:300]}")
        subfolder = data.get("subfolder", "")
        return f"{subfolder}/{name}".strip("/")

    async def get_history(self, prompt_id: str) -> dict | None:
        data = await self._request("GET", f"/history/{prompt_id}")
        return data.get(prompt_id) if data else None

    async def download(self, filename: str, subfolder: str = "", img_type: str = "output") -> bytes:
        return await self._request(  # type: ignore[no-any-return]
            "GET",
            "/view",
            params={"filename": filename, "subfolder": subfolder, "type": img_type},
        )

    # ---- 等待完成：WS 优先，轮询兜底 ----

    async def wait_result(
        self,
        prompt_id: str,
        *,
        on_progress: ProgressCallback | None = None,
        timeout: float = 600.0,
        use_ws: bool = True,
    ) -> dict:
        if use_ws:
            try:
                return await self._wait_ws(prompt_id, on_progress=on_progress, timeout=timeout)
            except Exception as exc:  # noqa: BLE001 WS 失败一律退化为轮询
                logger.warning("ComfyUI WebSocket 不可用（{}），改用 /history 轮询", exc)
        return await self._wait_polling(prompt_id, on_progress=on_progress, timeout=timeout)

    async def _wait_ws(
        self, prompt_id: str, *, on_progress: ProgressCallback | None, timeout: float
    ) -> dict:
        import websockets

        deadline = time.monotonic() + timeout
        async with websockets.connect(self.ws_url, open_timeout=10) as ws:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProviderError("等待 ComfyUI 结果超时")
                msg = json.loads(await asyncio.wait_for(ws.recv(), remaining))
                msg_type = msg.get("type")
                data = msg.get("data", {})
                if msg_type == "progress" and on_progress and data.get("max"):
                    on_progress(data.get("value", 0) / data["max"])
                elif msg_type == "executed" and data.get("prompt_id") == prompt_id:
                    return await self._require_history(prompt_id)
                elif msg_type == "execution_error" and data.get("prompt_id") == prompt_id:
                    raise ProviderError(
                        f"ComfyUI 执行失败: {data.get('exception_message', str(data)[:300])}"
                    )

    async def _wait_polling(
        self, prompt_id: str, *, on_progress: ProgressCallback | None, timeout: float
    ) -> dict:
        deadline = time.monotonic() + timeout
        ticks = 0
        while time.monotonic() < deadline:
            entry = await self.get_history(prompt_id)
            if entry is not None:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise ProviderError(f"ComfyUI 执行失败: {str(status)[:300]}")
                return entry
            ticks += 1
            if on_progress:
                on_progress(min(0.95, ticks * 0.02))  # 无真实进度时的估计值
            await asyncio.sleep(1.0)
        raise ProviderError("等待 ComfyUI 结果超时")

    async def _require_history(self, prompt_id: str) -> dict:
        entry = await self.get_history(prompt_id)
        if entry is None:
            raise ProviderError("ComfyUI 已完成但取不到 history")
        return entry
