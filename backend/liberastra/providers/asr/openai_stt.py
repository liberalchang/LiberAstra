"""OpenAI 兼容 ASR 适配器：标准 /v1/audio/transcriptions。

覆盖 OpenAI、Groq、Speaches / faster-whisper-server、SiliconFlow SenseVoice。
请求 verbose_json 以获得分段时间戳；服务端不支持时退化为整段文本。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from liberastra.providers.base import ASRResult, ASRSegment, ProviderError
from liberastra.providers.llm.openai_compatible import _json_request


class OpenAISTT:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        default_model: str = "whisper-1",
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 300.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self._client = client
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    async def transcribe(
        self,
        *,
        file_path: str,
        language: str | None = None,
        task: str = "transcribe",
        model: str | None = None,
        **params: Any,
    ) -> ASRResult:
        endpoint = "translations" if task == "translate" else "transcriptions"
        path = Path(file_path)
        data: dict[str, Any] = {
            "model": model or self.default_model,
            "response_format": "verbose_json",
            **params,
        }
        if language:
            data["language"] = language

        own_client = self._client is None
        http = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            with path.open("rb") as fh:
                resp = await http.post(
                    f"{self.base_url}/audio/{endpoint}",
                    headers=self._headers(),
                    data=data,
                    files={"file": (path.name, fh)},
                )
            if resp.status_code >= 400:
                raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            payload = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"无法连接 {self.base_url}: {exc}") from exc
        finally:
            if own_client:
                await http.aclose()

        segments = [
            ASRSegment(
                start=float(s.get("start", 0.0)),
                end=float(s.get("end", 0.0)),
                text=str(s.get("text", "")).strip(),
            )
            for s in payload.get("segments", [])
        ]
        return ASRResult(
            text=str(payload.get("text", "")).strip(),
            segments=segments,
            language=payload.get("language"),
        )

    async def list_models(self) -> list[str]:
        """拉取 /models，供识别页下拉。没有该端点时由调用方改成手填。"""
        data = await _json_request(
            self._client, self._timeout, "GET", f"{self.base_url}/models", self._headers()
        )
        rows = data.get("data", []) if isinstance(data, dict) else []
        if not isinstance(rows, list):
            return []
        return [str(item["id"]) for item in rows if isinstance(item, dict) and item.get("id")]

    async def test(self) -> str:
        models = await self.list_models()
        return f"连接成功，可用模型 {len(models)} 个"
