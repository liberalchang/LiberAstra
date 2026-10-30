"""调用本仓库 services/depth 的 HTTP 接口。

深度模型跑在独立进程里（本机插件或局域网显卡主机），主服务不加载权重。
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from liberastra.providers.base import ProviderError

_DEFAULT_MODEL = "dpt_swin2_large_384"


class LiberDepth:
    """Liber Depth API：健康检查、模型列表、单张图片转深度图。"""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or None
        self._client = client

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        timeout = kwargs.pop("timeout", httpx.Timeout(30.0, read=600.0))
        headers = {**self._headers(), **kwargs.pop("headers", {})}
        if self._client is not None:
            return await self._client.request(method, url, headers=headers, timeout=timeout, **kwargs)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.request(method, url, headers=headers, **kwargs)

    async def test(self) -> str:
        try:
            response = await self._request("GET", "/api/v1/health", timeout=10.0)
        except httpx.HTTPError as exc:
            raise ProviderError(f"连不上 Liber Depth：{exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(f"Liber Depth 健康检查失败：HTTP {response.status_code}")
        body = response.json()
        device = body.get("device") or "unknown"
        models = body.get("models") or []
        return f"深度服务可用（{device}，{len(models)} 个模型）"

    async def list_models(self) -> list[str]:
        try:
            response = await self._request("GET", "/api/v1/models", timeout=15.0)
        except httpx.HTTPError as exc:
            raise ProviderError(f"拉取深度模型失败：{exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(f"拉取深度模型失败：HTTP {response.status_code}")
        body = response.json()
        ids: list[str] = []
        for item in body.get("models") or []:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
            elif isinstance(item, str) and item.strip():
                ids.append(item.strip())
        default = str(body.get("default_model") or _DEFAULT_MODEL)
        if default and default not in ids:
            ids.insert(0, default)
        return ids or [_DEFAULT_MODEL]

    async def convert_depth(
        self,
        content: bytes,
        filename: str,
        *,
        model: str = "",
        device: str = "",
    ) -> tuple[str, bytes]:
        """返回 (服务端文件名, PNG 字节)。调用方仍按原图名另存为 *_depth.png。"""
        files = {"image": (filename or "image.png", content, "application/octet-stream")}
        data = {"model": model or "", "device": device or ""}
        try:
            response = await self._request("POST", "/api/v1/depth/convert", files=files, data=data)
        except httpx.HTTPError as exc:
            raise ProviderError(f"深度图转换失败：{exc}") from exc
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = str(response.json().get("detail") or detail)
            except Exception:
                pass
            raise ProviderError(detail or f"深度图转换失败：HTTP {response.status_code}")
        body = response.json()
        encoded = body.get("png_base64") or ""
        if not encoded:
            raise ProviderError("深度服务没有返回图片")
        name = str(body.get("filename") or "depth.png")
        return name, base64.b64decode(encoded)
