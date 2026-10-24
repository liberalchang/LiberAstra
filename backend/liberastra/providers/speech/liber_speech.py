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
from liberastra.storage.local import resolve

# Liber Speech API 直接支持的容器格式。mp3 由本进程用 ffmpeg 从 wav 转出。
_DIRECT_FORMATS = {"wav": "wav", "ogg": "ogg_opus", "ogg_opus": "ogg_opus", "opus": "ogg_opus"}
# Chatterbox multilingual 接受的 language_id。短字符串不一定是语言，例如音色编号 1。
_LANG_CODES = (
    "ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "it", "ja", "ko",
    "ms", "nl", "no", "pl", "pt", "ru", "sv", "sw", "tr", "zh",
)
# 旧值 multilingual 等同 Multilingual V2。未知 id 不在这里改写。
SPEECH_ALIASES = {"multilingual": "multilingual_v2"}
# 单语言包和英文模型锁定 language_id；多语言模型为 None，走调用方选择的 23 种语言。
SPEECH_MODEL_LANGS: dict[str, str | None] = {
    "multilingual_v3": None,
    "multilingual_v2": None,
    "turbo": "en",
    "nano": "en",
    "standard": "en",
    "zh-cmn": "zh",
    "es-mx": "es",
    "pt-br": "pt",
    "es-es": "es",
    "pt-pt": "pt",
    "hi": "hi",
}


def _catalog_items(raw: object) -> list[dict[str, Any]]:
    """保留语音服务返回的 id、显示名、分组和语言。"""
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        entry: dict[str, Any] = {
            "id": model_id,
            "label": str(item.get("label") or model_id).strip() or model_id,
        }
        group = str(item.get("group") or "").strip()
        if group:
            entry["group"] = group
        languages = item.get("languages")
        if isinstance(languages, list):
            entry["languages"] = [str(code).strip() for code in languages if str(code).strip()]
        items.append(entry)
    return items


def canonical_asr_model(model: str) -> str:
    """校验识别模型。空值表示跟随语音服务的 LIBER_SPEECH_ASR_MODEL。"""
    raw = (model or "").strip()
    if raw.lower() in {"", "default"}:
        return ""
    key = raw.lower()
    aliases = {
        "faster-whisper-large-v3": "large-v3",
        "systran/faster-whisper-large-v3": "large-v3",
        "turbo": "large-v3-turbo",
        "faster-whisper-large-v3-turbo": "large-v3-turbo",
        "systran/faster-whisper-large-v3-turbo": "large-v3-turbo",
        "mobiuslabsgmbh/faster-whisper-large-v3-turbo": "large-v3-turbo",
        "qwen3-asr": "qwen3-asr-1.7b",
        "qwen/qwen3-asr-1.7b": "qwen3-asr-1.7b",
    }
    key = aliases.get(key, key)
    if key not in {"large-v3", "large-v3-turbo", "qwen3-asr-1.7b"}:
        raise ValueError(f"未知语音转文字模型 {model}")
    return key


def canonical_speech_model(model: str) -> str:
    """校验并展开别名。未知 id 抛出 ValueError。"""
    key = SPEECH_ALIASES.get(model.strip(), model.strip())
    if key not in SPEECH_MODEL_LANGS:
        raise ValueError(f"未知语音模型 {model}")
    return key


def speech_form_model(model: str) -> str:
    """写入合成表单的模型名。别名展开，未知 id 原样传出。"""
    raw = (model or "").strip()
    return SPEECH_ALIASES.get(raw, raw)


def speech_language(model: str, voice: str, explicit: str | None = None) -> str:
    """单语言包和英文模型用固定语言，多语言模型跟随音色或显式语言。"""
    mid = SPEECH_ALIASES.get((model or "").strip(), (model or "").strip())
    locked = SPEECH_MODEL_LANGS.get(mid)
    if mid in SPEECH_MODEL_LANGS and locked:
        return locked
    return language_from_voice(voice, explicit)


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
    """从语言代码或 zh-CN 这类前缀得到 language_id。识别不了时用 zh。"""
    if explicit and explicit.strip():
        code = explicit.strip().split("-")[0].lower()
        if code in _LANG_CODES:
            return code
    token = (voice or "").strip()
    if token:
        head = token.split("-")[0].lower()
        if head in _LANG_CODES:
            return head
    return "zh"


class LiberSpeech:
    """同时实现 TTS 与 ASR 协议，对应同一个 Liber Speech API 实例。"""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        default_model: str = "multilingual_v3",
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 300.0,
        default_asr_model: str = "",
    ) -> None:
        self.api_root = _api_root(base_url or "http://127.0.0.1:5555")
        self.api_key = api_key
        self.default_model = default_model or "multilingual_v3"
        self.default_asr_model = canonical_asr_model(default_asr_model)
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
            raise ProviderError(f"Liber Speech API HTTP {resp.status_code} {url}: {detail}")
        return resp

    async def test(self) -> str:
        resp = await self._request("GET", f"{self.api_root}/health")
        data = resp.json()
        asr = "已加载" if data.get("asr_ready") else "尚未加载"
        tts = "已加载" if data.get("tts_ready") else "尚未加载"
        return f"Liber Speech API {data.get('status', 'ok')}，ASR {asr}，TTS {tts}"

    async def list_models(self) -> list[str]:
        """向语音服务询问实际加载的 ASR / TTS 模型。地址错误时这里会失败。"""
        resp = await self._request("GET", f"{self.api_root}/models")
        payload = resp.json()
        items = payload.get("models") if isinstance(payload, dict) else None
        names: list[str] = []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str) and item.strip():
                    names.append(item.strip())
                    continue
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                role = str(item.get("role") or "").strip()
                if name and role:
                    names.append(f"{name} · {role}")
                elif name:
                    names.append(name)
        if not names:
            raise ProviderError(f"Liber Speech API 未返回模型 {self.api_root}/models")
        return names

    async def list_catalog(self) -> dict[str, Any]:
        """读取可选模型清单。tts_models 与 asr_models 来自语音服务，不是本地写死的列表。"""
        resp = await self._request("GET", f"{self.api_root}/models")
        payload = resp.json()
        if not isinstance(payload, dict):
            raise ProviderError(f"Liber Speech API 模型响应无效 {self.api_root}/models")
        tts_models = _catalog_items(payload.get("tts_models"))
        asr_models = _catalog_items(payload.get("asr_models"))
        if not tts_models or not asr_models:
            raise ProviderError(f"Liber Speech API 未返回 tts_models 或 asr_models {self.api_root}/models")
        return {
            "tts_models": tts_models,
            "asr_models": asr_models,
            "default_tts_model": str(payload.get("default_tts_model") or "").strip(),
            "default_asr_model": str(payload.get("default_asr_model") or "").strip(),
        }

    async def list_voices(self) -> list[str]:
        """合成时的语言代码，例如 zh、en。这不是模型列表。"""
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
        chosen = speech_form_model(model or self.default_model)
        language = speech_language(chosen, voice, params.get("language"))
        form = {
            "text": text,
            "model": chosen,
            "language": language,
            "format": speech_fmt,
        }
        ref_audio = str(params.get("ref_audio") or "").strip()
        if ref_audio:
            path = resolve(ref_audio)
            if not path.is_file():
                raise ProviderError(f"参考音频不存在: {path.name}")
            with path.open("rb") as fh:
                resp = await self._request(
                    "POST",
                    f"{self.api_root}/tts/synthesize",
                    data=form,
                    files={"prompt": (path.name, fh, "application/octet-stream")},
                )
        else:
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
        model: str | None = None,
        **params: Any,
    ) -> ASRResult:
        path = Path(file_path)
        data: dict[str, Any] = {"task": task, **params}
        if language:
            data["language"] = language
        # 空值和 OpenAI 默认名 whisper-1 走系统设置，仍为空则由语音服务 .env 决定。
        chosen = (model or "").strip()
        if chosen.lower() in {"", "default", "whisper", "whisper-1"}:
            chosen = self.default_asr_model
        if chosen:
            data["model"] = chosen
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


def _wav_to_mp3_sync(wav: bytes) -> bytes:
    """用线程跑 ffmpeg。Windows 的事件循环不支持 asyncio 子进程。"""
    if not shutil.which("ffmpeg"):
        raise ProviderError(
            "Liber Speech API 输出 wav 或 ogg_opus。当前请求是 mp3，"
            "本机没有 ffmpeg，请把输出格式改成 wav。"
        )
    import subprocess

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.wav"
        dst = Path(tmp) / "out.mp3"
        src.write_bytes(wav)
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-codec:a", "libmp3lame", str(dst)],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0 or not dst.is_file():
            tail = proc.stderr.decode(errors="replace")[-400:]
            raise ProviderError(f"wav 转 mp3 失败: {tail}")
        return dst.read_bytes()


async def _wav_to_mp3(wav: bytes) -> bytes:
    """Liber Speech API 没有 mp3。页面默认格式是 mp3 时，在本机转一次。"""
    import asyncio

    return await asyncio.to_thread(_wav_to_mp3_sync, wav)
