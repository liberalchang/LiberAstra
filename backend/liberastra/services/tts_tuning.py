"""TTS 画布节点的“高级参数 + 相关调节”映射。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_PRESETS = (
    {"id": "calm", "at": 0.0, "speed": 0.9, "exaggeration": 0.35, "cfg_weight": 0.55},
    {"id": "natural", "at": 1 / 3, "speed": 1.0, "exaggeration": 0.5, "cfg_weight": 0.5},
    {"id": "broadcast", "at": 2 / 3, "speed": 1.05, "exaggeration": 0.65, "cfg_weight": 0.45},
    {"id": "excited", "at": 1.0, "speed": 1.15, "exaggeration": 0.9, "cfg_weight": 0.35},
)


def _clamp(value: Any, minimum: float, maximum: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def tuning_at(expressiveness: Any) -> dict[str, float]:
    value = _clamp(expressiveness, 0.0, 1.0, 1 / 3)
    left = _PRESETS[0]
    right = _PRESETS[-1]
    for index in range(len(_PRESETS) - 1):
        if value <= _PRESETS[index + 1]["at"]:
            left = _PRESETS[index]
            right = _PRESETS[index + 1]
            break
    span = float(right["at"]) - float(left["at"])
    ratio = 0.0 if span <= 0 else (value - float(left["at"])) / span
    return {
        "speed": round(
            float(left["speed"]) + (float(right["speed"]) - float(left["speed"])) * ratio,
            3,
        ),
        "exaggeration": round(
            float(left["exaggeration"])
            + (float(right["exaggeration"]) - float(left["exaggeration"])) * ratio,
            3,
        ),
        "cfg_weight": round(
            float(left["cfg_weight"])
            + (float(right["cfg_weight"]) - float(left["cfg_weight"])) * ratio,
            3,
        ),
    }


def supports_emotion_model(model: str | None) -> bool:
    model_id = (model or "").split(" · ")[0].strip().lower()
    return model_id not in {"turbo", "nano"}


def tts_options(
    tuning: Mapping[str, Any] | None,
    supports_emotion: bool,
) -> dict[str, float]:
    if not tuning or not tuning.get("advanced"):
        return {}
    if supports_emotion and tuning.get("linked"):
        values = tuning_at(tuning.get("expressiveness"))
    else:
        values = {
            "speed": _clamp(tuning.get("speed"), 0.8, 1.2, 1.0),
            "exaggeration": _clamp(tuning.get("exaggeration"), 0.2, 1.0, 0.5),
            "cfg_weight": _clamp(tuning.get("cfgWeight"), 0.3, 0.7, 0.5),
        }
    options = {"speed": values["speed"]}
    if supports_emotion:
        options["exaggeration"] = values["exaggeration"]
        options["cfg_weight"] = values["cfg_weight"]
    return options
