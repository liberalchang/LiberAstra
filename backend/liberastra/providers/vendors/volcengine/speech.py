"""火山豆包语音 HTTP 单向合成。

识别接口是二进制 WebSocket 帧，本适配器只登记模型并在转写时返回明确错误，
避免把未验证的帧格式发给线上服务。
"""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any

import httpx

from liberastra.providers.base import ASRResult, ProviderError

DEFAULT_BASE = "https://openspeech.bytedance.com"
TTS_RESOURCE = "seed-tts-2.0"


class DoubaoSpeech:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 120.0,
        default_speaker: str = "zh_female_vv_uranus_bigtts",
    ) -> None:
        self.base_url = (base_url or DEFAULT_BASE).rstrip("/")
        self.api_key = api_key
        self._client = client
        self._timeout = timeout
        self.default_speaker = default_speaker

    def _headers(self, resource: str) -> dict[str, str]:
        if not self.api_key:
            raise ProviderError("火山豆包语音需要 API Key")
        return {
            "X-Api-Key": self.api_key,
            "X-Api-Resource-Id": resource,
            "X-Api-Request-Id": uuid.uuid4().hex,
            "Content-Type": "application/json",
        }

    async def test(self) -> str:
        await self.synthesize(text="测", voice=self.default_speaker, model="doubao-seed-tts-2.0")
        return "火山豆包语音可连接"

    async def list_voices(self) -> list[str]:
        return [self.default_speaker]

    async def list_models(self) -> list[str]:
        return ["doubao-seed-tts-2.0", "doubao-seed-asr-2.0"]

    async def synthesize(
        self,
        *,
        text: str,
        voice: str,
        model: str | None = None,
        fmt: str = "mp3",
        **params: Any,
    ) -> bytes:
        del params
        if model and "asr" in model:
            raise ProviderError("识别模型不能用于语音合成")
        audio_format = "mp3" if fmt in {"mp3", "wav"} else "mp3"
        body = {
            "user": {"uid": "liberastra"},
            "req_params": {
                "text": text,
                "speaker": voice or self.default_speaker,
                "audio_params": {"format": audio_format, "sample_rate": 24000},
            },
        }
        own = self._client is None
        http = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            resp = await http.post(
                f"{self.base_url}/api/v3/tts/unidirectional",
                headers=self._headers(TTS_RESOURCE),
                json=body,
            )
            if resp.status_code >= 400:
                raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            audio = collect_tts_audio(resp.text)
        except httpx.HTTPError as exc:
            raise ProviderError(f"无法连接豆包语音: {exc}") from exc
        finally:
            if own:
                await http.aclose()
        if not audio:
            raise ProviderError("豆包语音未返回音频")
        return audio

    async def transcribe(
        self,
        *,
        file_path: str,
        language: str | None = None,
        task: str = "transcribe",
        model: str | None = None,
        **params: Any,
    ) -> ASRResult:
        del params, model
        raise ProviderError(
            "豆包语音识别（doubao-seed-asr-2.0）使用二进制 WebSocket，"
            f"当前未提交转写。任务 {task}，文件 {file_path}，语言 {language or 'auto'}。"
        )


def collect_tts_audio(payload: str) -> bytes:
    """单向接口返回多行 JSON，音频在 data 的 base64 字段里。"""
    chunks: list[bytes] = []
    for line in payload.splitlines():
        line = line.strip()
        if not line or line.startswith("event:"):
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        encoded = ""
        data = row.get("data")
        if isinstance(data, str):
            encoded = data
        elif isinstance(data, dict):
            encoded = str(data.get("audio") or data.get("data") or "")
        if encoded:
            try:
                chunks.append(base64.b64decode(encoded))
            except ValueError:
                continue
        code = row.get("code")
        if code not in (None, 0, 20000000) and not chunks:
            raise ProviderError(f"豆包语音合成失败: {row.get('message') or row}")
    return b"".join(chunks)
