"""edge-tts 适配器：微软在线 TTS（需 edge-tts>=7.3.1，支持 Sec-MS-GEC v2）。"""

from __future__ import annotations

from typing import Any

from liberastra.providers.base import ProviderError

# ComfyUI-EdgeTTS 下拉值形如 "[Chinese] zh-CN Xiaoxiao"
_DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


def speed_to_rate(speed: Any) -> str:
    """语速 0.5–2.0 → edge-tts rate，如 +0% / -20%。"""
    try:
        value = float(speed)
    except (TypeError, ValueError):
        return "+0%"
    pct = int(round((value - 1.0) * 100))
    return f"{pct:+d}%"


def comfy_voice_to_neural(voice: str | None) -> str:
    """把 Comfy EdgeTTS 音色标签映射为 edge-tts 的 Neural 短名。"""
    raw = (voice or "").strip()
    if not raw:
        return _DEFAULT_VOICE
    if raw.endswith("Neural") and " " not in raw and not raw.startswith("["):
        return raw
    if raw.startswith("[") and "]" in raw:
        raw = raw.split("]", 1)[1].strip()
    parts = raw.split()
    if len(parts) >= 2:
        locale, name = parts[0], "".join(parts[1:])
        if not name.endswith("Neural"):
            name += "Neural"
        return f"{locale}-{name}"
    return raw


class EdgeTTS:
    """零配置微软 Edge 在线 TTS，仅输出 mp3。"""

    def __init__(self, default_voice: str = _DEFAULT_VOICE) -> None:
        self.default_voice = default_voice

    async def synthesize(
        self,
        *,
        text: str,
        voice: str,
        model: str | None = None,  # noqa: ARG002 edge-tts 无模型概念
        fmt: str = "mp3",
        rate: str = "+0%",
        **_params: Any,
    ) -> bytes:
        if fmt != "mp3":
            raise ProviderError("edge_tts 仅支持 mp3 输出，请选择 mp3 格式")
        import edge_tts

        chosen = comfy_voice_to_neural(voice) if voice else self.default_voice
        communicate = edge_tts.Communicate(text, chosen, rate=rate)
        chunks: list[bytes] = []
        try:
            async for message in communicate.stream():
                if message["type"] == "audio":
                    chunks.append(message["data"])
        except Exception as exc:  # noqa: BLE001 edge_tts 抛出多种网络异常
            raise ProviderError(f"edge-tts 合成失败: {exc}") from exc
        audio = b"".join(chunks)
        if not audio:
            raise ProviderError("edge-tts 未返回音频")
        return audio

    async def list_voices(self) -> list[str]:
        """拉取微软全部 Neural 音色短名（与 Comfy EdgeTTS 同级数量级）。"""
        import edge_tts

        try:
            voices = await edge_tts.list_voices()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"edge-tts 获取音色失败: {exc}") from exc
        names = [str(v["ShortName"]) for v in voices if v.get("ShortName")]
        # 中文音色靠前，其余按短名排序
        zh = sorted(n for n in names if n.startswith("zh-"))
        rest = sorted(n for n in names if not n.startswith("zh-"))
        return zh + rest

    async def list_models(self) -> list[str]:
        return await self.list_voices()

    async def list_model_folder(self, folder: str) -> list[str]:
        """供工作流 options_from=voices 拉取下拉选项。"""
        if folder in ("voices", "edge_tts:voices"):
            return await self.list_voices()
        raise ProviderError(f"edge_tts 不支持目录 {folder}，请用 voices")

    async def test(self) -> str:
        voices = await self.list_voices()
        return f"edge-tts 可用，音色 {len(voices)} 个"
