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


def _has_audio_stream_sync(path: Path) -> bool:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-select_streams", "a",
            "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path),
        ],
        capture_output=True,
        check=False,
    )
    return bool(proc.stdout.decode().strip())


async def has_audio_stream(path: Path) -> bool:
    """文件里是否有音轨。没有音轨时混音和原声替换要走另一条命令。"""
    return await asyncio.to_thread(_has_audio_stream_sync, path)


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


async def trim_video(video: Path, out: Path, seconds: float, *, fps: float = 24) -> None:
    """裁到指定秒数，并统一成相同的帧率与编码，方便多段直接拼接。"""
    _require_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    await _run(
        "ffmpeg", "-y", "-i", str(video),
        "-t", f"{max(seconds, 0.05):.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart",
        str(out),
    )


async def extract_last_frame(video: Path, out: Path, *, fps: float = 24) -> None:
    """抽出成片最后一帧，作为下一段数字人的首帧。

    先探测时长，再从末尾往前约一帧精确取画面。输入侧 -sseof 在很短的片段上
    会落到没有画面的位置，所以 -ss 放在 -i 之后。取不到时再往前退一点。
    """
    _require_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    duration = await probe_duration(video)
    step = 1.0 / fps if fps > 0 else 0.04
    for start in (max(0.0, duration - step), max(0.0, duration - 0.2), 0.0):
        if out.exists():
            out.unlink()
        await _run(
            "ffmpeg", "-y", "-i", str(video),
            "-ss", f"{start:.3f}",
            "-frames:v", "1", "-update", "1",
            str(out),
        )
        if out.exists() and out.stat().st_size > 0:
            return
    raise ProviderError("未能抽出视频尾帧")


async def slice_audio(audio: Path, start: float, duration: float, out: Path) -> None:
    """按时间切出一段音频。单句长到无法再切字时，用它把配音拆开。"""
    _require_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    suffix = out.suffix.lower()
    if suffix == ".wav":
        audio_args = ["-c:a", "pcm_s16le"]
    elif suffix in {".m4a", ".aac"}:
        audio_args = ["-c:a", "aac", "-b:a", "192k"]
    else:
        audio_args = ["-c:a", "libmp3lame", "-q:a", "2"]
    await _run(
        "ffmpeg", "-y", "-i", str(audio),
        "-ss", f"{max(start, 0.0):.3f}", "-t", f"{max(duration, 0.05):.3f}",
        "-vn", *audio_args, str(out),
    )


async def add_bgm(
    *,
    video: Path,
    bgm: Path,
    out: Path,
    bgm_volume: float = 0.2,
) -> None:
    """给视频混入 BGM。有原声时按比例叠加；没有音轨时直接铺上音乐。"""
    _require_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    volume = max(0.0, min(1.0, bgm_volume))
    if await has_audio_stream(video):
        filter_complex = (
            f"[1:a]volume={volume}[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[a]"
        )
        extra = []
    else:
        # 音乐比画面短时补静音，避免 -shortest 把画面裁掉
        filter_complex = f"[1:a]volume={volume},apad[a]"
        extra = ["-shortest"]
    await _run(
        "ffmpeg", "-y",
        "-i", str(video), "-i", str(bgm),
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac",
        *extra,
        str(out),
    )


async def replace_audio(video: Path, audio_source: Path, out: Path) -> None:
    """用另一条媒体的音轨替换成片声音，画面直接拷贝。"""
    _require_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    if not await has_audio_stream(audio_source):
        raise ProviderError("参考视频没有音轨")
    await _run(
        "ffmpeg", "-y",
        "-i", str(video), "-i", str(audio_source),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out),
    )


async def slice_video(
    video: Path,
    start: float,
    duration: float,
    out: Path,
    *,
    fps: float = 24,
    frames: int | None = None,
) -> None:
    """按时间切出一段视频并统一帧率。有音轨就保留，没有就只出画面。"""
    _require_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    audio_args = (
        ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"]
        if await has_audio_stream(video)
        else ["-an"]
    )
    frame_args = ["-frames:v", str(frames)] if frames else []
    await _run(
        "ffmpeg", "-y", "-i", str(video),
        "-ss", f"{max(start, 0.0):.3f}",
        "-t", f"{max(duration, 0.05):.3f}",
        "-r", str(fps),
        *frame_args,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        *audio_args,
        str(out),
    )


def _fit_frame_filter(
    width: int,
    height: int,
    subtitle: Path | None,
    subtitle_size: float,
    subtitle_color: str,
) -> str:
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )
    if subtitle is not None:
        vf += f",subtitles='{_escape_filter_path(subtitle)}'{_force_style(subtitle_size, subtitle_color)}"
    return vf


async def make_native_clip_segment(
    *,
    clip: Path,
    out: Path,
    width: int,
    height: int,
    subtitle: Path | None = None,
    subtitle_size: float = 0,
    subtitle_color: str = "",
    fps: int = DEFAULT_FPS,
) -> None:
    """保留片段自带音轨，只统一画幅和帧率。没有音轨时补一条静音，方便后面拼接。"""
    _require_ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = _fit_frame_filter(width, height, subtitle, subtitle_size, subtitle_color)
    if await has_audio_stream(clip):
        await _run(
            "ffmpeg", "-y", "-i", str(clip),
            "-vf", vf,
            "-map", "0:v:0", "-map", "0:a:0",
            "-c:v", "libx264",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-pix_fmt", "yuv420p", "-r", str(fps),
            str(out),
        )
        return
    await _run(
        "ffmpeg", "-y", "-i", str(clip),
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-vf", vf,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-shortest",
        str(out),
    )
