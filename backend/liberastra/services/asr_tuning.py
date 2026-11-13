"""ASR 画布节点与页面高级参数的模型映射。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

_TIMESTAMPS = {"none", "segment", "word"}
_TASKS = {"transcribe", "translate"}


def asr_model_kind(model: str | None) -> str:
    return "qwen" if "qwen" in (model or "").lower() else "whisper"


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


def _temperature(value: Any) -> list[float] | None:
    if isinstance(value, list | tuple):
        items = list(value)
    elif isinstance(value, str):
        items = value.split(",")
    else:
        items = [value]
    numbers: list[float] = []
    for item in items:
        try:
            numbers.append(round(float(item), 3))
        except (TypeError, ValueError):
            continue
    return numbers or None


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


def asr_options(
    tuning: Mapping[str, Any] | None, model: str | None
) -> dict[str, Any]:
    if not tuning or not tuning.get("advanced"):
        return {}
    kind = asr_model_kind(model)
    options: dict[str, Any] = {}

    timestamps = tuning.get("timestamps")
    if timestamps in _TIMESTAMPS:
        options["timestamps"] = timestamps
    if kind == "qwen":
        if tuning.get("qwenBatchSize") is not None:
            options["max_inference_batch_size"] = _clamp_int(
                tuning.get("qwenBatchSize"), 1, 32
            )
    else:
        task = tuning.get("task")
        if task in _TASKS:
            options["task"] = task
        if tuning.get("vad"):
            options["vad_filter"] = True
        if tuning.get("beamSize") is not None:
            options["beam_size"] = _clamp_int(tuning.get("beamSize"), 1, 10)
        if tuning.get("bestOf") is not None:
            options["best_of"] = _clamp_int(tuning.get("bestOf"), 1, 10)
        if tuning.get("temperature") is not None:
            temperature = _temperature(tuning.get("temperature"))
            if temperature:
                options["temperature"] = temperature
        if tuning.get("noSpeechThreshold") is not None:
            options["no_speech_threshold"] = _clamp_float(
                tuning.get("noSpeechThreshold"), 0.0, 1.0
            )
        if tuning.get("compressionRatioThreshold") is not None:
            options["compression_ratio_threshold"] = _clamp_float(
                tuning.get("compressionRatioThreshold"), 0.0, 10.0
            )
        if tuning.get("conditionOnPreviousText") is False:
            options["condition_on_previous_text"] = False
        for key, target in (
            ("initialPrompt", "initial_prompt"),
            ("hotwords", "hotwords"),
        ):
            text = str(tuning.get(key) or "").strip()
            if text:
                options[target] = text

    options.update(_extra(tuning.get("extraJson")))
    return options
