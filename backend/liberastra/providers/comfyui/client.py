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


def _is_transient_comfy_error(exc: BaseException) -> bool:
    """单次 HTTP 超时/瞬时断连：长任务（如本地 MiniMax H3）期间 Comfy 忙时常见，应重试而非整任务失败。"""
    if isinstance(exc, httpx.TimeoutException):
        return True
    msg = str(exc)
    return "请求超时" in msg or "ReadTimeout" in msg or "ConnectTimeout" in msg


def _with_friendly_hint(text: str) -> str:
    """常见 ComfyUI 报错追加中文提示，帮助定位（模型选错、缺节点等）。"""
    hints = [
        (
            "Expected 3D",
            "疑似选错模型：视频工作流需要 Wan/MiniMax 系视频模型，当前选中的是平面图像模型",
        ),
        (
            "got [2, 4,",
            "疑似选错模型：视频工作流需要 Wan/MiniMax 系视频模型，当前选中的是平面图像模型",
        ),
        (
            "prompt_outputs_failed_validation",
            "工作流缺少必填输入或节点版本不匹配，请检查该包与本地 ComfyUI 插件版本",
        ),
        (
            "Required input is missing",
            "工作流节点缺必填输入，通常是包与本地插件版本不一致",
        ),
    ]
    for needle, hint in hints:
        if needle in text:
            return f"{text}（{hint}）"
    return text


def _format_comfy_status_error(status: dict[str, Any]) -> str:
    """从 history.status 抽出可读错误（优先 execution_error.exception_message）。"""
    for msg in status.get("messages") or []:
        if not isinstance(msg, (list, tuple)) or len(msg) < 2:
            continue
        if msg[0] != "execution_error":
            continue
        detail = msg[1] if isinstance(msg[1], dict) else {}
        parts = [
            detail.get("node_type"),
            f"node={detail.get('node_id')}" if detail.get("node_id") is not None else None,
            (detail.get("exception_message") or "").strip() or None,
        ]
        text = " ".join(p for p in parts if p)
        if text:
            return _with_friendly_hint(text[:500])
    return str(status)[:300]


class ComfyClient:
    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 120.0,
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
                raise ProviderError(
                    f"ComfyUI HTTP {resp.status_code}: {_with_friendly_hint(resp.text[:500])}"
                )
            if resp.headers.get("content-type", "").startswith("application/json"):
                return resp.json()
            return resp.content
        except httpx.TimeoutException as exc:
            # ReadTimeout 的 str 经常为空，必须带上类型名
            raise ProviderError(
                f"ComfyUI 请求超时 {self.base_url}{path}（>{self._timeout:.0f}s，{type(exc).__name__}）"
            ) from exc
        except httpx.HTTPError as exc:
            detail = str(exc).strip() or type(exc).__name__
            raise ProviderError(f"无法连接 ComfyUI {self.base_url}: {detail}") from exc
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

    async def list_model_folder(self, folder: str) -> list[str]:
        """列出某个模型目录的文件名（即 ComfyUI 节点下拉框里的取值）。"""
        files = await self._request("GET", f"/models/{folder}")
        if not isinstance(files, list):
            raise ProviderError(f"ComfyUI 返回了意外的模型目录内容: {str(files)[:200]}")
        return [f for f in files if isinstance(f, str)]

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

    async def cancel_prompt(self, prompt_id: str) -> None:
        """取消排队或运行中的 prompt，不在 ComfyUI 上留孤儿任务。

        先尝试从队列删除（排队中的直接移除）；若已在运行则 interrupt 当前执行。
        所有失败都静默——取消是尽力而为，不能掩盖原始错误。
        """
        try:
            await self._request("POST", "/queue", json={"delete": [prompt_id]})
        except ProviderError:
            pass
        try:
            queue = await self.queue_info()
            running = [item[1] for item in queue.get("queue_running", []) if len(item) > 1]
            if prompt_id in running:
                await self.interrupt()
        except ProviderError:
            pass

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
        """等待 prompt 完成。超时或任务被取消时先在 ComfyUI 侧取消，不遗留孤儿任务。

        注意：ProviderError（超时/执行失败）不再退化为轮询——否则超时会重新计满一轮。
        """
        try:
            if use_ws:
                try:
                    return await self._wait_ws(prompt_id, on_progress=on_progress, timeout=timeout)
                except ProviderError:
                    raise  # 超时/执行失败：直接抛出，不退化轮询
                except Exception as exc:  # noqa: BLE001 仅 WS 通道不可用才退化
                    logger.warning("ComfyUI WebSocket 不可用（{}），改用 /history 轮询", exc)
            return await self._wait_polling(prompt_id, on_progress=on_progress, timeout=timeout)
        except asyncio.CancelledError:
            await self.cancel_prompt(prompt_id)
            raise
        except ProviderError as exc:
            if "超时" in str(exc):
                await self.cancel_prompt(prompt_id)
            raise

    async def _wait_ws(
        self, prompt_id: str, *, on_progress: ProgressCallback | None, timeout: float
    ) -> dict:
        import websockets

        # 竞态：连上 WS 前任务可能已跑完；history 瞬时超时不阻断 WS
        done = await self._history_if_done(prompt_id, soft=True)
        if done is not None:
            return done

        deadline = time.monotonic() + timeout
        poll_every = 2.0
        async with websockets.connect(self.ws_url, open_timeout=10) as ws:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProviderError("等待 ComfyUI 结果超时")
                try:
                    raw = await asyncio.wait_for(ws.recv(), min(poll_every, remaining))
                except TimeoutError:
                    # 漏收 execution_success / 中途断流时用 history 兜底
                    done = await self._history_if_done(prompt_id, soft=True)
                    if done is not None:
                        return done
                    continue

                msg = json.loads(raw)
                msg_type = msg.get("type")
                data = msg.get("data", {})
                if data.get("prompt_id") not in (None, prompt_id):
                    continue
                if msg_type == "progress" and on_progress and data.get("max"):
                    on_progress(data.get("value", 0) / data["max"])
                elif msg_type == "execution_error":
                    raise ProviderError(
                        f"ComfyUI 执行失败: {_with_friendly_hint(str(data.get('exception_message', str(data)[:300])))}"
                    )
                elif msg_type == "execution_success":
                    return await self._require_history(prompt_id)
                elif msg_type == "executing" and data.get("node") is None:
                    # Comfy 约定：node 为空表示整图执行结束
                    return await self._require_history(prompt_id)

    async def _wait_polling(
        self, prompt_id: str, *, on_progress: ProgressCallback | None, timeout: float
    ) -> dict:
        deadline = time.monotonic() + timeout
        ticks = 0
        while time.monotonic() < deadline:
            done = await self._history_if_done(prompt_id, soft=True)
            if done is not None:
                return done
            ticks += 1
            if on_progress:
                on_progress(min(0.95, ticks * 0.02))  # 无真实进度时的估计值
            await asyncio.sleep(1.0)
        raise ProviderError("等待 ComfyUI 结果超时")

    async def _history_if_done(self, prompt_id: str, *, soft: bool = False) -> dict | None:
        try:
            entry = await self.get_history(prompt_id)
        except ProviderError as exc:
            if soft and _is_transient_comfy_error(exc):
                logger.warning("ComfyUI /history 瞬时失败，继续等待：{}", exc)
                return None
            raise
        if entry is None:
            return None
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            raise ProviderError(f"ComfyUI 执行失败: {_format_comfy_status_error(status)}")
        # history 出现即视为已结束（success / 无 status 的旧版）
        return entry

    async def _require_history(self, prompt_id: str) -> dict:
        # 完成后短暂重试：Comfy 偶发 success 事件早于 history 落盘
        for attempt in range(5):
            entry = await self._history_if_done(prompt_id, soft=True)
            if entry is not None:
                return entry
            await asyncio.sleep(0.5 * (attempt + 1))
        raise ProviderError("ComfyUI 已完成但取不到 history")
