"""Ollama 原生适配器：/api/tags 拉模型列表与健康检查；chat 走 /v1 兼容端点。"""

from __future__ import annotations

import httpx

from liberastra.providers.llm.openai_compatible import OpenAICompatibleLLM, _json_request


class OllamaLLM(OpenAICompatibleLLM):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 300.0,
    ) -> None:
        self.native_base = base_url.rstrip("/")
        super().__init__(f"{self.native_base}/v1", None, client=client, timeout=timeout)

    async def list_models(self) -> list[str]:
        data = await _json_request(
            self._client, self._timeout, "GET", f"{self.native_base}/api/tags", self._headers()
        )
        return sorted(m["name"] for m in data.get("models", []) if "name" in m)

    async def test(self) -> str:
        models = await self.list_models()
        return f"Ollama 连接成功，本地模型 {len(models)} 个"
