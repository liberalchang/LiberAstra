"""ffmpeg 媒体层测试（本机无 ffmpeg 时跳过）。"""

import asyncio
import base64
import shutil
import wave
from pathlib import Path

import pytest

from liberastra.media import ffmpeg

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="需要 ffmpeg")

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _wav(path: Path, seconds: float = 0.5, rate: int = 8000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))


def test_trim_last_frame_and_slice(tmp_path: Path) -> None:
    async def run() -> None:
        raw = tmp_path / "raw.mp4"
        await ffmpeg._run(
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=160x120:d=1",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(raw),
        )
        trimmed = tmp_path / "trim.mp4"
        await ffmpeg.trim_video(raw, trimmed, 0.4, fps=24)
        duration = await ffmpeg.probe_duration(trimmed)
        assert 0.2 < duration < 0.7
        frame = tmp_path / "last.png"
        await ffmpeg.extract_last_frame(trimmed, frame)
        assert frame.stat().st_size > 8

        audio = tmp_path / "a.wav"
        _wav(audio, 1.0)
        piece = tmp_path / "piece.wav"
        await ffmpeg.slice_audio(audio, 0.2, 0.3, piece)
        sliced = await ffmpeg.probe_duration(piece)
        assert 0.2 < sliced < 0.5

    asyncio.run(run())


def test_make_segment_and_concat(tmp_path: Path) -> None:
    async def run() -> None:
        image = tmp_path / "a.png"
        image.write_bytes(PNG_1PX)
        audio = tmp_path / "a.wav"
        _wav(audio, 0.5)

        srt = tmp_path / "a.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:00,500\n你好\n", encoding="utf-8")

        seg1 = tmp_path / "seg1.mp4"
        await ffmpeg.make_segment(
            image=image, audio=audio, out=seg1, width=320, height=240, subtitle=srt
        )
        assert seg1.exists() and seg1.stat().st_size > 0
        duration = await ffmpeg.probe_duration(seg1)
        assert 0.4 < duration < 1.0

        seg2 = tmp_path / "seg2.mp4"
        await ffmpeg.make_segment(image=image, audio=audio, out=seg2, width=320, height=240)

        out = tmp_path / "out.mp4"
        await ffmpeg.concat_segments([seg1, seg2], out, list_file=tmp_path / "list.txt")
        total = await ffmpeg.probe_duration(out)
        assert total > duration

        bgm = tmp_path / "bgm.wav"
        _wav(bgm, 1.0)
        final = tmp_path / "final.mp4"
        await ffmpeg.add_bgm(video=out, bgm=bgm, out=final, bgm_volume=0.3)
        assert final.exists() and final.stat().st_size > 0

    asyncio.run(run())
