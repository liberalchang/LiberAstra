"""edge-tts 适配器：微软在线 TTS，零配置可用，作为默认兜底。

输出为 mp3 流；其他格式由平台层用 ffmpeg 转码（M2 仅支持 mp3 直通）。
"""

from __future__ import annotations

from typing import Any

from liberastra.providers.base import ProviderError

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


class EdgeTTS:
    def __init__(self, default_voice: str = DEFAULT_VOICE) -> None:
        self.default_voice = default_voice

    async def synthesize(
        self,
        *,
        text: str,
        voice: str,
        model: str | None = None,  # noqa: ARG002 edge-tts 无模型概念
        fmt: str = "mp3",
        **params: Any,
    ) -> bytes:
        if fmt != "mp3":
            raise ProviderError("edge_tts 仅支持 mp3 输出，请选择 mp3 格式")
        import edge_tts

        rate = params.get("rate", "+0%")
        communicate = edge_tts.Communicate(text, voice or self.default_voice, rate=rate)
        chunks: list[bytes] = []
        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
        except Exception as exc:  # noqa: BLE001 edge_tts 抛出多种网络异常
            raise ProviderError(f"edge-tts 合成失败: {exc}") from exc
        if not chunks:
            raise ProviderError("edge-tts 未返回音频")
        return b"".join(chunks)

    async def list_voices(self) -> list[str]:
        import edge_tts

        try:
            voices = await edge_tts.list_voices()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"edge-tts 获取音色失败: {exc}") from exc
        return sorted(v["ShortName"] for v in voices)

    async def test(self) -> str:
        voices = await self.list_voices()
        return f"edge-tts 可用，音色 {len(voices)} 个"
