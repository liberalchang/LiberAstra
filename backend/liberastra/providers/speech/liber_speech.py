"""调用本仓库 services/speech 的 HTTP 接口。

语音模型跑在独立进程里（可部署在局域网显卡主机），主服务不加载权重。
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from liberastra.providers.base import ASRResult, ASRSegment, ProviderError

# Liber Speech API 直接支持的容器格式。mp3 由本进程用 ffmpeg 从 wav 转出。
_DIRECT_FORMATS = {"wav": "wav", "ogg": "ogg_opus", "ogg_opus": "ogg_opus", "opus": "ogg_opus"}
_LANG_CODES = ("zh", "en", "ja", "ko", "fr", "de", "es")


def _api_root(base_url: str) -> str:
    root = base_url.rstrip("/")
    if root.endswith("/api/v1"):
        return root
    return f"{root}/api/v1"


def _origin(api_root: str) -> str:
    """从 http://host:5555/api/v1 取出 http://host:5555，用来拼接相对下载地址。"""
    marker = "/api/v1"
    if api_root.endswith(marker):
        return api_root[: -len(marker)]
    return api_root


def language_from_voice(voice: str, explicit: str | None = None) -> str:
    """Liber Speech 的多语言模型用语言代码，不用 Edge 那种音色名。"""
    if explicit and explicit.strip():
        return explicit.strip().split("-")[0].lower()
    token = (voice or "").strip()
    if not token:
        return "zh"
    head = token.split("-")[0].lower()
    if head in _LANG_CODES or len(token) <= 5:
        return head
    lowered = token.lower()
    for code in _LANG_CODES:
        if lowered.startswith(code):
            return code
    return "zh"


class LiberSpeech:
    """同时实现 TTS 与 ASR 协议，对应同一个 Liber Speech API 实例。"""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        default_model: str = "multilingual",
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 300.0,
    ) -> None:
        self.api_root = _api_root(base_url or "http://127.0.0.1:5555")
        self.api_key = api_key
        self.default_model = default_model or "multilingual"
        self._client = client
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        own_client = self._client is None
        http = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            resp = await http.request(method, url, headers=self._headers(), **kwargs)
            await resp.aread()
        except httpx.HTTPError as exc:
            raise ProviderError(f"无法连接 Liber Speech API {self.api_root}: {exc}") from exc
        finally:
            if own_client:
                await http.aclose()
        if resp.status_code >= 400:
            detail = resp.text[:500]
            raise ProviderError(f"Liber Speech API HTTP {resp.status_code}: {detail}")
        return resp

    async def test(self) -> str:
        resp = await self._request("GET", f"{self.api_root}/health")
        data = resp.json()
        asr = "已加载" if data.get("asr_ready") else "尚未加载"
        tts = "已加载" if data.get("tts_ready") else "尚未加载"
        return f"Liber Speech API {data.get('status', 'ok')}，ASR {asr}，TTS {tts}"

    async def list_voices(self) -> list[str]:
        """该服务按语言代码选声音，不提供 Edge 风格的音色列表。"""
        return list(_LANG_CODES)

    async def synthesize(
        self,
        *,
        text: str,
        voice: str,
        model: str | None = None,
        fmt: str = "mp3",
        **params: Any,
    ) -> bytes:
        speech_fmt = _DIRECT_FORMATS.get(fmt, "wav")
        language = language_from_voice(voice, params.get("language"))
        form = {
            "text": text,
            "model": model or self.default_model,
            "language": language,
            "format": speech_fmt,
        }
        resp = await self._request("POST", f"{self.api_root}/tts/synthesize", data=form)
        payload = resp.json()
        audio_url = str(payload.get("audio_url") or "")
        if not audio_url:
            raise ProviderError("Liber Speech API 未返回 audio_url")
        if audio_url.startswith("/"):
            audio_url = urljoin(_origin(self.api_root) + "/", audio_url.lstrip("/"))
        audio = (await self._request("GET", audio_url)).content
        if fmt == "mp3" and speech_fmt == "wav":
            return await _wav_to_mp3(audio)
        return audio

    async def transcribe(
        self,
        *,
        file_path: str,
        language: str | None = None,
        task: str = "transcribe",
        model: str | None = None,  # noqa: ARG002 Liber Speech API 的模型在服务端配置
        **params: Any,
    ) -> ASRResult:
        path = Path(file_path)
        data: dict[str, Any] = {"task": task, **params}
        if language:
            data["language"] = language
        with path.open("rb") as fh:
            resp = await self._request(
                "POST",
                f"{self.api_root}/asr/transcribe",
                data=data,
                files={"file": (path.name, fh)},
            )
        payload = resp.json()
        segments = [_segment(chunk) for chunk in payload.get("chunks") or []]
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        return ASRResult(
            text=str(payload.get("text", "")).strip(),
            segments=segments,
            language=meta.get("language") or language,
        )


def _segment(chunk: dict[str, Any]) -> ASRSegment:
    start = chunk.get("start", 0.0)
    end = chunk.get("end", 0.0)
    timestamp = chunk.get("timestamp")
    if isinstance(timestamp, (list, tuple)) and len(timestamp) == 2:
        start = timestamp[0] if timestamp[0] is not None else start
        end = timestamp[1] if timestamp[1] is not None else end
    return ASRSegment(
        start=float(start or 0.0),
        end=float(end or 0.0),
        text=str(chunk.get("text", "")).strip(),
    )


async def _wav_to_mp3(wav: bytes) -> bytes:
    """Liber Speech API 没有 mp3。页面默认格式是 mp3 时，在本机转一次。"""
    if not shutil.which("ffmpeg"):
        raise ProviderError(
            "Liber Speech API 输出 wav 或 ogg_opus。当前请求是 mp3，"
            "本机没有 ffmpeg，请把输出格式改成 wav。"
        )
    import asyncio

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.wav"
        dst = Path(tmp) / "out.mp3"
        src.write_bytes(wav)
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(src), "-codec:a", "libmp3lame", str(dst),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0 or not dst.is_file():
            tail = stderr.decode(errors="replace")[-400:]
            raise ProviderError(f"wav 转 mp3 失败: {tail}")
        return dst.read_bytes()
