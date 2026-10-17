"""ffmpeg 媒体合成层：分段合成、字幕烧录（libass）、拼接、BGM 混音。

直接调用系统 ffmpeg/ffprobe CLI（Docker 镜像已内置）。
Windows 上 uvicorn 可能用 SelectorEventLoop（不支持 asyncio 子进程），
因此统一在线程里跑同步 subprocess。
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from liberastra.providers.base import ProviderError

DEFAULT_FPS = 30


def _require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise ProviderError("未找到 ffmpeg，请安装后重试")


def _run_sync(cmd: str, *args: str) -> None:
    proc = subprocess.run(
        [cmd, *args],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        tail = proc.stderr.decode(errors="replace")[-500:]
        raise ProviderError(f"{cmd} 执行失败: {tail}")


async def _run(cmd: str, *args: str) -> None:
    await asyncio.to_thread(_run_sync, cmd, *args)


def _probe_duration_sync(path: Path) -> float:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(path),
        ],
        capture_output=True,
        check=False,
    )
    try:
        return float(proc.stdout.decode().strip())
    except ValueError as exc:
        raise ProviderError(f"无法读取媒体时长: {path}") from exc


async def probe_duration(path: Path) -> float:
    """媒体时长（秒）。"""
    return await asyncio.to_thread(_probe_duration_sync, path)


def _escape_filter_path(path: Path) -> str:
    """ffmpeg filter 内的路径转义（libass subtitles），兼容 Windows 盘符。"""
    posix = path.resolve().as_posix()
    return posix.replace(":", "\\:").replace("'", "\\'")


def _ass_color(hex_color: str) -> str:
    """#RRGGBB → libass PrimaryColour（&H00BBGGRR，BGR 序）。非法值返回空串。"""
    h = hex_color.lstrip("#")
    if len(h) != 6 or any(c not in "0123456789abcdefABCDEF" for c in h):
        return ""
    rr, gg, bb = h[0:2], h[2:4], h[4:6]
    return f"&H00{bb.upper()}{gg.upper()}{rr.upper()}"


def _force_style(subtitle_size: float, subtitle_color: str = "") -> str:
    """字幕 force_style 片段：字号与颜色，0/空 表示用 libass 默认。"""
    parts: list[str] = []
    if subtitle_size > 0:
        parts.append(f"FontSize={int(subtitle_size)}")
    ass = _ass_color(subtitle_color)
    if ass:
        parts.append(f"PrimaryColour={ass}")
    return f":force_style='{','.join(parts)}'" if parts else ""


async def make_segment(
    *,
    image: Path,
    audio: Path,
    out: Path,
    width: int,
    height: int,
    subtitle: Path | None = None,
    subtitle_size: float = 0,
    subtitle_color: str = "",
    fps: int = DEFAULT_FPS,
) -> None:
    """静态图 + 音频合成一个视频分段，可选烧录字幕。subtitle_size>0 指定字号，subtitle_color 指定颜色。"""
    _require_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )
    if subtitle is not None:
        vf += f",subtitles='{_escape_filter_path(subtitle)}'{_force_style(subtitle_size, subtitle_color)}"
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


async def make_clip_segment(
    *,
    clip: Path,
    audio: Path,
    out: Path,
    width: int,
    height: int,
    subtitle: Path | None = None,
    subtitle_size: float = 0,
    subtitle_color: str = "",
    fps: int = DEFAULT_FPS,
) -> None:
    """AI 视频片段 + 配音合成分段：片段循环到配音时长，可选烧录字幕。"""
    _require_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )
    if subtitle is not None:
        vf += f",subtitles='{_escape_filter_path(subtitle)}'{_force_style(subtitle_size, subtitle_color)}"
    await _run(
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(clip),
        "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-vf", vf,
        "-c:v", "libx264",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-shortest", str(out),
    )


async def make_silence(path: Path, seconds: float) -> None:
    """生成指定时长的静音 mp3（标题卡等无配音分段用）。"""
    _require_ffmpeg()
    path.parent.mkdir(parents=True, exist_ok=True)
    await _run(
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", str(seconds), "-q:a", "9", str(path),
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
