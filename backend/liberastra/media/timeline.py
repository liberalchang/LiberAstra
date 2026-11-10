"""时长/帧数换算的唯一真相源：本地包按帧对齐，云端模型按秒。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

_FRAMES_KEYS = ("length", "frames")


@dataclass(frozen=True)
class DurationSpec:
    unit: Literal["frames", "seconds"]
    fps: float | None = None
    minimum: float | None = None  # 与 unit 同单位
    maximum: float | None = None
    align_base: int = 0
    align_offset: int = 0
    step: float = 1.0  # 仅 seconds 单位使用
    auto: bool = False  # 云端 -1


@dataclass(frozen=True)
class ResolvedDuration:
    value: int | float  # 按 unit 返回；auto 时保留 -1
    seconds: float | None  # auto 时为 None
    frames: int | None  # 仅 frames 单位
    clamped: bool
    reason: str  # "", "aligned", "clamped_min", "clamped_max", "auto"


def frames_for_duration(duration: float, fps: float, spec: dict[str, Any]) -> int:
    """把秒数向上吸附到工作流允许的帧数。MiniMax H3 为 17k+5。"""
    if fps <= 0:
        fps = 24.0
    base = int(spec.get("align_base") or 0)
    offset = int(spec.get("align_offset") or 0)
    minimum = int(spec.get("min") or 1)
    maximum = int(spec.get("max") or 0) or 10**9
    target = max(1, math.ceil(max(0.0, duration) * fps))
    if base > 0:
        k = math.ceil(max(0, target - offset) / base)
        frames = base * k + offset
        if frames < minimum:
            k = math.ceil(max(0, minimum - offset) / base)
            frames = base * k + offset
    else:
        frames = target
    return max(minimum, min(maximum, frames))


def max_aligned_seconds(fps: float, spec: dict[str, Any]) -> float:
    """单段能完整播完的最长秒数：不超过 max、且满足对齐规则的最大帧数 / fps。"""
    if fps <= 0:
        fps = 24.0
    maximum = int(spec.get("max") or 0)
    if maximum <= 0:
        return 600.0
    base = int(spec.get("align_base") or 0)
    offset = int(spec.get("align_offset") or 0)
    minimum = int(spec.get("min") or 1)
    if base > 0:
        k = max(0, (maximum - offset) // base)
        frames = base * k + offset
        if frames < minimum:
            frames = minimum
    else:
        frames = maximum
    return frames / fps


def _spec_dict(spec: DurationSpec) -> dict[str, Any]:
    return {
        "min": spec.minimum or 1,
        "max": spec.maximum or 0,
        "align_base": spec.align_base,
        "align_offset": spec.align_offset,
    }


def _align_up(target: int, spec: DurationSpec) -> int:
    if spec.align_base <= 0:
        return max(1, target)
    k = math.ceil(max(0, target - spec.align_offset) / spec.align_base)
    frames = spec.align_base * k + spec.align_offset
    minimum = int(spec.minimum or 1)
    if frames < minimum:
        k = math.ceil(max(0, minimum - spec.align_offset) / spec.align_base)
        frames = spec.align_base * k + spec.align_offset
    return frames


def _clamp_frames(frames: int, spec: DurationSpec) -> int:
    minimum = int(spec.minimum or 1)
    maximum = int(spec.maximum or 0)
    if maximum <= 0:
        return max(minimum, frames)
    if frames <= maximum:
        return max(minimum, frames)
    if spec.align_base > 0:
        k = max(0, (maximum - spec.align_offset) // spec.align_base)
        candidate = spec.align_base * k + spec.align_offset
        if candidate >= minimum:
            return candidate
    return maximum


def resolve_duration(spec: DurationSpec, desired_seconds: float) -> ResolvedDuration:
    if spec.auto and desired_seconds < 0:
        return ResolvedDuration(value=-1, seconds=None, frames=None, clamped=False, reason="auto")
    if spec.unit == "seconds":
        step = spec.step or 1.0
        value: int | float = round(max(0.0, desired_seconds) / step) * step
        if float(step).is_integer():
            value = int(value)
        clamped = False
        if spec.minimum is not None and value < spec.minimum:
            value = spec.minimum
            clamped = True
        if spec.maximum is not None and value > spec.maximum:
            value = spec.maximum
            clamped = True
        return ResolvedDuration(
            value=value,
            seconds=float(value),
            frames=None,
            clamped=clamped,
            reason="clamped" if clamped else "",
        )

    fps = spec.fps or 24.0
    target = max(1, math.ceil(max(0.0, desired_seconds) * fps))
    aligned = _align_up(target, spec)
    frames = _clamp_frames(aligned, spec)
    reason = "aligned" if aligned != target else ""
    if frames != aligned:
        reason = "clamped_min" if frames == int(spec.minimum or 1) else "clamped_max"
    return ResolvedDuration(
        value=frames,
        seconds=frames / fps,
        frames=frames,
        clamped=frames != aligned,
        reason=reason,
    )


def duration_spec_for_pack(pack: Any) -> DurationSpec | None:
    inputs = getattr(pack, "inputs", None) or {}
    spec: dict[str, Any] | None = None
    for key in _FRAMES_KEYS:
        candidate = inputs.get(key)
        if isinstance(candidate, dict):
            spec = candidate
            break
    fps = getattr(pack, "fps", None)
    if spec is None or not fps:
        return None
    return DurationSpec(
        unit="frames",
        fps=float(fps),
        minimum=spec.get("min"),
        maximum=spec.get("max"),
        align_base=int(spec.get("align_base") or 0),
        align_offset=int(spec.get("align_offset") or 0),
    )


def duration_spec_for_model(param: dict[str, Any] | None) -> DurationSpec | None:
    if not param:
        return None
    minimum = param.get("min")
    return DurationSpec(
        unit="seconds",
        minimum=minimum,
        maximum=param.get("max"),
        step=float(param.get("step") or 1.0),
        auto=minimum == -1,
    )


def duration_limits(spec: DurationSpec | None) -> dict[str, Any] | None:
    if spec is None:
        return None
    if spec.unit == "frames":
        fps = spec.fps or 24.0
        minimum = int(spec.minimum or 1)
        maximum_seconds = max_aligned_seconds(fps, _spec_dict(spec))
        hint = (
            f"按 {spec.align_base}n+{spec.align_offset} 帧吸附，最长 {maximum_seconds:.2f} 秒"
            if spec.align_base > 0
            else f"最长 {maximum_seconds:.2f} 秒"
        )
        return {
            "unit": "seconds",
            "min": minimum / fps,
            "max": maximum_seconds,
            "align_base": spec.align_base,
            "align_offset": spec.align_offset,
            "fps": fps,
            "aligned": spec.align_base > 0,
            "hint": hint,
        }
    hint = f"最长 {spec.maximum:g} 秒" if spec.maximum is not None else ""
    if spec.auto:
        hint = f"{hint}；-1 = 自动" if hint else "-1 = 自动"
    return {
        "unit": "seconds",
        "min": spec.minimum,
        "max": spec.maximum,
        "step": spec.step,
        "auto": spec.auto,
        "aligned": False,
        "hint": hint,
    }


def duration_limits_for_pack(pack: Any) -> dict[str, Any] | None:
    return duration_limits(duration_spec_for_pack(pack))
