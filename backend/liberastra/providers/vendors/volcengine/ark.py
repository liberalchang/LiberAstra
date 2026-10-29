"""火山方舟 HTTP 客户端：对话、图像、视频任务。

由 services/providers.py 的 build_adapter 在 type=volcengine_ark 时构造。
图像走 POST /images/generations，视频走 POST/GET /contents/generations/tasks。
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any

import httpx

from liberastra.providers.base import ProviderError
from liberastra.providers.llm.openai_compatible import _json_request
from liberastra.providers.vendors.volcengine.schemas import data_url, image_body, video_body

DEFAULT_BASE = "https://ark.cn-beijing.volces.com/api/v3"


class VolcengineArk:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = (base_url or DEFAULT_BASE).rstrip("/")
        self.api_key = api_key
        self._client = client
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ProviderError("火山方舟需要 API Key")
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def test(self) -> str:
        data = await _json_request(
            self._client, self._timeout, "GET", f"{self.base_url}/models", self._headers()
        )
        return f"火山方舟可连接，远端模型 {len(_model_ids(data))} 个"

    async def list_models(self) -> list[str]:
        data = await _json_request(
            self._client, self._timeout, "GET", f"{self.base_url}/models", self._headers()
        )
        return _model_ids(data)

    async def chat(
        self, *, model: str, messages: list[dict[str, Any]], **params: Any
    ) -> str:
        body = {"model": model, "messages": messages, **params}
        data = await _json_request(
            self._client,
            self._timeout,
            "POST",
            f"{self.base_url}/chat/completions",
            self._headers(),
            json=body,
        )
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"火山方舟对话响应缺少文本: {str(data)[:300]}") from exc

    async def generate(
        self,
        *,
        prompt: str,
        size: str = "2K",
        n: int = 1,
        model: str | None = None,
        **params: Any,
    ) -> list[tuple[str, bytes]]:
        if not model:
            raise ProviderError("火山方舟图像生成需要指定模型")
        images = _image_inputs(params)
        body = image_body(
            model=model,
            prompt=prompt,
            size=str(params.get("size") or size),
            output_format=str(params.get("output_format") or "png"),
            watermark=bool(params.get("watermark", False)),
            images=images or None,
            sequential=str(params.get("sequential_image_generation") or "disabled"),
        )
        if n > 1 and "sequential_image_generation" not in params:
            body["sequential_image_generation"] = "auto"
        data = await _json_request(
            self._client,
            max(self._timeout, 180.0),
            "POST",
            f"{self.base_url}/images/generations",
            self._headers(),
            json=body,
        )
        return await self._download_images(data)

    async def edit(
        self,
        *,
        image: tuple[str, bytes],
        prompt: str,
        size: str = "2K",
        model: str | None = None,
        **params: Any,
    ) -> list[tuple[str, bytes]]:
        filename, content = image
        extra = [str(item) for item in (params.get("images") or []) if item]
        params = {**params, "images": [data_url(filename, content), *extra]}
        return await self.generate(prompt=prompt, size=size, model=model, **params)

    async def generate_video(
        self,
        *,
        model: str,
        prompt: str,
        sub_capability: str,
        images: dict[str, list[str]] | None = None,
        videos: list[str] | None = None,
        audios: list[str] | None = None,
        on_progress: Any = None,
        wait_timeout: float = 900.0,
        **params: Any,
    ) -> tuple[str, bytes]:
        body = video_body(
            model=model,
            prompt=prompt,
            sub_capability=sub_capability,
            images=images,
            videos=videos,
            audios=audios,
            resolution=str(params.get("resolution") or "720p"),
            ratio=str(params.get("ratio") or "16:9"),
            duration=int(params.get("duration") or 5),
            generate_audio=bool(params.get("generate_audio", True)),
            camera_fixed=bool(params.get("camera_fixed", False)),
            watermark=bool(params.get("watermark", False)),
            seed=int(params.get("seed") or -1),
        )
        created = await _json_request(
            self._client,
            self._timeout,
            "POST",
            f"{self.base_url}/contents/generations/tasks",
            self._headers(),
            json=body,
        )
        task_id = str(created.get("id") or "")
        if not task_id:
            raise ProviderError(f"火山方舟未返回视频任务 ID: {str(created)[:300]}")
        return await self._poll_video(task_id, on_progress=on_progress, wait_timeout=wait_timeout)

    async def _poll_video(
        self, task_id: str, *, on_progress: Any, wait_timeout: float
    ) -> tuple[str, bytes]:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait_timeout
        while True:
            data = await _json_request(
                self._client,
                self._timeout,
                "GET",
                f"{self.base_url}/contents/generations/tasks/{task_id}",
                self._headers(),
            )
            status = str(data.get("status") or "")
            if on_progress is not None:
                on_progress(0.3 if status == "queued" else 0.6 if status == "running" else 0.9)
            if status == "succeeded":
                url = str((data.get("content") or {}).get("video_url") or "")
                if not url:
                    raise ProviderError("视频任务成功但没有 video_url")
                return "video.mp4", await self._download(url)
            if status in {"failed", "cancelled", "expired"}:
                raise ProviderError(f"火山方舟视频任务{status}: {str(data.get('error') or data)[:400]}")
            if loop.time() > deadline:
                raise ProviderError(f"火山方舟视频任务超时（>{wait_timeout:.0f}s）: {task_id}")
            await asyncio.sleep(5)

    async def _download_images(self, data: dict[str, Any]) -> list[tuple[str, bytes]]:
        images: list[tuple[str, bytes]] = []
        for index, item in enumerate(data.get("data") or []):
            if item.get("b64_json"):
                images.append((f"image_{index}.png", base64.b64decode(item["b64_json"])))
            elif item.get("url"):
                images.append((f"image_{index}.png", await self._download(item["url"])))
        if not images:
            raise ProviderError(f"火山方舟未返回图片: {str(data)[:300]}")
        return images

    async def _download(self, url: str) -> bytes:
        own = self._client is None
        http = self._client or httpx.AsyncClient(timeout=max(self._timeout, 180.0))
        try:
            resp = await http.get(url)
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPError as exc:
            raise ProviderError(f"下载火山方舟产物失败: {exc}") from exc
        finally:
            if own:
                await http.aclose()


def _model_ids(data: Any) -> list[str]:
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    ids: list[str] = []
    for row in rows:
        if isinstance(row, dict) and row.get("id"):
            ids.append(str(row["id"]))
        elif isinstance(row, str):
            ids.append(row)
    return ids


def _image_inputs(params: dict[str, Any]) -> list[str]:
    raw = params.get("images") or params.get("image")
    if isinstance(raw, str) and raw:
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    return []
