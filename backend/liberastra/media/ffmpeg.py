"""ffmpeg 媒体合成层：分段合成、字幕烧录（libass）、拼接、BGM 混音。

直接调用系统 ffmpeg/ffprobe CLI（Docker 镜像已内置）。
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from liberastra.providers.base import ProviderError

DEFAULT_FPS = 30


def _require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise ProviderError("未找到 ffmpeg，请安装后重试")


async def _run(cmd: str, *args: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        cmd, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        tail = stderr.decode(errors="replace")[-500:]
        raise ProviderError(f"{cmd} 执行失败: {tail}")


async def probe_duration(path: Path) -> float:
    """媒体时长（秒）。"""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode().strip())
    except ValueError as exc:
        raise ProviderError(f"无法读取媒体时长: {path}") from exc


def _escape_filter_path(path: Path) -> str:
    """ffmpeg filter 内的路径转义（libass subtitles），兼容 Windows 盘符。"""
    posix = path.resolve().as_posix()
    return posix.replace(":", "\\:").replace("'", "\\'")


async def make_segment(
    *,
    image: Path,
    audio: Path,
    out: Path,
    width: int,
    height: int,
    subtitle: Path | None = None,
    fps: int = DEFAULT_FPS,
) -> None:
    """静态图 + 音频合成一个视频分段，可选烧录字幕。"""
    _require_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )
    if subtitle is not None:
        vf += f",subtitles='{_escape_filter_path(subtitle)}'"
    await _run(
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image),
        "-i", str(audio),
        "-vf", vf,
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-shortest", str(out),
    )


async def concat_segments(segments: list[Path], out: Path, *, list_file: Path) -> None:
    """无损拼接分段（concat demuxer，要求分段参数一致）。"""
    _require_ffmpeg()
    lines = [f"file '{p.resolve().as_posix()}'" for p in segments]
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    await _run(
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(out),
    )


async def add_bgm(
    *,
    video: Path,
    bgm: Path,
    out: Path,
    bgm_volume: float = 0.2,
) -> None:
    """给视频混入 BGM（原声 + BGM 按比例混音）。"""
    _require_ffmpeg()
    volume = max(0.0, min(1.0, bgm_volume))
    await _run(
        "ffmpeg", "-y",
        "-i", str(video), "-i", str(bgm),
        "-filter_complex",
        f"[1:a]volume={volume}[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac",
        str(out),
    )
