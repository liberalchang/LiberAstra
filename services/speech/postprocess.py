"""ffmpeg 后处理：变速、响度归一、参考音频切片。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class PostProcessError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise PostProcessError("ffmpeg_missing", "未找到 ffmpeg，无法执行音频后处理")


def speed_filter(speed: float) -> str:
    if not 0.5 <= speed <= 2.0:
        raise PostProcessError("invalid_speed", "speed 必须在 0.5 到 2.0 之间")
    return f"atempo={speed:g}"


def loudnorm_filter(target_lufs: float) -> str:
    if not -40.0 <= target_lufs <= -5.0:
        raise PostProcessError("invalid_lufs", "target_lufs 必须在 -40 到 -5 之间")
    return f"loudnorm=I={target_lufs:g}:TP=-1.5:LRA=11"


def build_speed_command(source: Path, target: Path, speed: float) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-filter:a",
        speed_filter(speed),
        "-c:a",
        "pcm_s16le",
        str(target),
    ]


def build_loudnorm_command(source: Path, target: Path, target_lufs: float) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-filter:a",
        loudnorm_filter(target_lufs),
        "-c:a",
        "pcm_s16le",
        str(target),
    ]


def build_slice_command(
    source: Path,
    target: Path,
    start: float,
    duration: float | None = None,
) -> list[str]:
    args = ["ffmpeg", "-y", "-ss", f"{start:g}", "-i", str(source)]
    if duration is not None and duration > 0:
        args.extend(["-t", f"{duration:g}"])
    args.extend(["-c:a", "pcm_s16le", str(target)])
    return args


def build_denoise_command(source: Path, target: Path) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-filter:a",
        "afftdn=nf=-25",
        "-c:a",
        "pcm_s16le",
        str(target),
    ]


def build_resample_command(source: Path, target: Path, sample_rate: int) -> list[str]:
    if not 8000 <= sample_rate <= 192000:
        raise PostProcessError("invalid_sample_rate", "sample_rate 必须在 8000 到 192000 之间")
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        str(target),
    ]


def _run(args: list[str]) -> None:
    _require_ffmpeg()
    proc = subprocess.run(args, capture_output=True, check=False)
    if proc.returncode != 0:
        tail = proc.stderr.decode(errors="replace")[-400:]
        raise PostProcessError("ffmpeg_failed", f"ffmpeg 处理失败: {tail}")


def apply_speed(path: Path, speed: float) -> Path:
    if abs(speed - 1.0) < 1e-9:
        return path
    temp = path.with_name(f".{path.stem}-speed{path.suffix}")
    _run(build_speed_command(path, temp, speed))
    temp.replace(path)
    return path


def apply_loudnorm(path: Path, target_lufs: float) -> Path:
    temp = path.with_name(f".{path.stem}-loudnorm{path.suffix}")
    _run(build_loudnorm_command(path, temp, target_lufs))
    temp.replace(path)
    return path


def apply_denoise(path: Path) -> Path:
    temp = path.with_name(f".{path.stem}-denoise{path.suffix}")
    _run(build_denoise_command(path, temp))
    temp.replace(path)
    return path


def apply_resample(path: Path, sample_rate: int) -> Path:
    if sample_rate <= 0:
        return path
    temp = path.with_name(f".{path.stem}-resample{path.suffix}")
    _run(build_resample_command(path, temp, sample_rate))
    temp.replace(path)
    return path


def slice_audio(
    source: Path,
    target: Path,
    start: float,
    duration: float | None = None,
) -> Path:
    _run(build_slice_command(source, target, start, duration))
    return target
