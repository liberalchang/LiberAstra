"""配音质量检查：检出 EdgeTTS 鉴权失败等导致的近静音文件。"""

from __future__ import annotations

import struct
import subprocess
import tempfile
from pathlib import Path

from liberastra.providers.base import ProviderError

# 16-bit PCM 峰值低于此视为近静音（正常语音峰值通常数千以上）
_SILENCE_PEAK = 100


def assert_audible(data: bytes, *, hint: str = "") -> None:
    """用 ffmpeg 解码后检查峰值；过小则抛错，避免静音成片流入后续步骤。"""
    if len(data) < 256:
        raise ProviderError("配音文件过小或为空" + (f"：{hint}" if hint else ""))

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.bin"
        raw = Path(tmp) / "pcm.s16"
        src.write_bytes(data)
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(src),
                "-f", "s16le", "-ac", "1", "-ar", "16000", str(raw),
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0 or not raw.is_file() or raw.stat().st_size < 2:
            tail = proc.stderr.decode(errors="replace")[-300:]
            raise ProviderError(f"配音无法解码: {tail}" + (f" ({hint})" if hint else ""))

        pcm = raw.read_bytes()
        n = len(pcm) // 2
        samples = struct.unpack(f"<{n}h", pcm[: n * 2])
        peak = max(abs(s) for s in samples) if samples else 0
        if peak < _SILENCE_PEAK:
            msg = (
                "配音为静音。若走 ComfyUI EdgeTTS：节点依赖的 edge-tts 需 >=7.3.1"
                "（微软 Sec-MS-GEC v2）；LiberAstra 已对 tts_edge 改走本机 edge-tts。"
            )
            if hint:
                msg = f"{msg} ({hint})"
            raise ProviderError(msg)
