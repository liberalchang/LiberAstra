"""ComfyUI 语音适配器：tts 能力的工作流包驱动（IndexTTS2 / EdgeTTS 等节点）。

EdgeTTS 节点本身只是调用微软云 API，不占 Comfy GPU。微软自 2026-10 起要求
Sec-MS-GEC v2；Comfy 侧若仍装 edge-tts<7.3.1 会写出静音 MP3。因此含 EdgeTTS
的包改由本机 edge-tts（>=7.3.1）直接合成。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from liberastra.media.audio_check import assert_audible
from liberastra.providers.base import ProviderError
from liberastra.providers.comfyui.client import ComfyClient
from liberastra.providers.comfyui.workflow import (
    download_files,
    extract_files,
    run_workflow_pack,
)
from liberastra.providers.tts.edge_tts import EdgeTTS, comfy_voice_to_neural, speed_to_rate
from liberastra.services.workflows import WorkflowPack


class ComfyUISpeech:
    """与 ComfyUIImage 同构：提交 tts 工作流包，取回音频字节。"""

    def __init__(self, base_url: str, *, client: ComfyClient | None = None) -> None:
        self.client = client or ComfyClient(base_url)

    async def synthesize_pack(
        self,
        *,
        pack: WorkflowPack,
        inputs: dict[str, Any],
        on_progress: Callable[[float], None] | None = None,
        wait_timeout: float | None = None,
    ) -> tuple[str, bytes]:
        """按工作流包合成，返回 (文件名, 字节)。"""
        # tts_edge：本机微软 Edge TTS，不提交远程 Comfy
        if pack.name == "tts_edge" or pack.requirements.get("package", "").startswith("edge-tts"):
            return await self._synthesize_edge_local(inputs, on_progress=on_progress)

        outputs = await run_workflow_pack(
            self.client, pack, inputs, on_progress=on_progress, wait_timeout=wait_timeout
        )
        audios = await download_files(self.client, extract_files(outputs, pack, ("audio", "audios")))
        if not audios:
            raise ProviderError("ComfyUI 完成但未产出音频")
        name, data = audios[0]
        assert_audible(data, hint=f"workflow={pack.name}")
        return name, data

    async def _synthesize_edge_local(
        self,
        inputs: dict[str, Any],
        *,
        on_progress: Callable[[float], None] | None = None,
    ) -> tuple[str, bytes]:
        text = str(inputs.get("text") or "").strip()
        if not text:
            raise ProviderError("EdgeTTS 朗读文本为空")
        if on_progress:
            on_progress(0.1)
        voice = comfy_voice_to_neural(str(inputs.get("voice") or ""))
        rate = speed_to_rate(inputs.get("speed"))
        audio = await EdgeTTS().synthesize(text=text, voice=voice, fmt="mp3", rate=rate)
        assert_audible(audio, hint="edge-tts local")
        if on_progress:
            on_progress(1.0)
        return "edge_tts.mp3", audio

    async def synthesize(self, **_kwargs: Any) -> bytes:
        raise ProviderError("ComfyUI 语音需要在请求里指定 tts 工作流包")

    async def test(self) -> str:
        return await self.client.test()

    async def list_models(self) -> list[str]:
        return await self.client.list_model_files()

    async def list_model_folder(self, folder: str) -> list[str]:
        return await self.client.list_model_folder(folder)
