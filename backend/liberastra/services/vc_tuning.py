"""VC 画布节点与页面高级参数的模型映射。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def vc_model_kind(model: str | None) -> str:
    return "seedvc" if "seed" in (model or "").lower() else "chatterbox"


def _clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _clamp_float(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _extra(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def vc_options(
    tuning: Mapping[str, Any] | None, model: str | None
) -> dict[str, Any]:
    if not tuning or not tuning.get("advanced"):
        return {}
    kind = vc_model_kind(model)
    options: dict[str, Any] = {}

    if tuning.get("convertAll"):
        options["convert_all"] = True
    for key, target, minimum in (
        ("segmentPadding", "segment_padding", 0.0),
        ("mergeGap", "merge_gap", 0.0),
        ("minSegment", "min_segment", 0.0),
        ("refStart", "ref_start", 0.0),
        ("refDuration", "ref_duration", 0.0),
    ):
        if tuning.get(key) is not None:
            options[target] = _clamp_float(tuning.get(key), minimum, 3600.0)

    normalize = bool(tuning.get("normalizeLoudness"))
    if normalize:
        options["normalize_loudness"] = True
        if tuning.get("targetLufs") is not None:
            options["target_lufs"] = _clamp_float(tuning.get("targetLufs"), -40.0, -5.0)
    if tuning.get("denoise"):
        options["denoise"] = True
    if tuning.get("outputSampleRate"):
        options["output_sample_rate"] = _clamp_int(
            tuning.get("outputSampleRate"), 0, 192000
        )

    if kind == "seedvc":
        if tuning.get("seed") is not None:
            options["seed"] = _clamp_int(tuning.get("seed"), 0, 2147483647)
        for key, target, minimum, maximum, integer in (
            ("diffusionSteps", "diffusion_steps", 1, 50, True),
            ("inferenceCfgRate", "inference_cfg_rate", 0.0, 2.0, False),
            ("nQuantizers", "n_quantizers", 1, 8, True),
            ("temperature", "temperature", 0.1, 2.0, False),
            ("lengthAdjust", "length_adjust", 0.9, 1.1, False),
            ("overlapFrameLen", "overlap_frame_len", 4, 64, True),
            ("maxWindow", "max_window", 5.0, 30.0, False),
            ("context", "context", 0.0, 0.5, False),
            ("fade", "fade", 0.0, 0.1, False),
            ("refMaxLen", "ref_max_len", 5.0, 30.0, False),
        ):
            if tuning.get(key) is None:
                continue
            if integer:
                options[target] = _clamp_int(tuning.get(key), int(minimum), int(maximum))
            else:
                options[target] = _clamp_float(tuning.get(key), float(minimum), float(maximum))

    options.update(_extra(tuning.get("extraJson")))
    return options
