"""参数类型转换、默认值填充和交叉校验。"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import params

_INT_RE = re.compile(r"^[+-]?\d+$")


@dataclass(frozen=True)
class ValidationIssue:
    param: str
    code: str
    message: str
    value: Any = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "param": self.param,
            "code": self.code,
            "message": self.message,
        }
        if self.value is not None:
            data["value"] = self.value
        return data


class ParamValidationError(ValueError):
    def __init__(
        self,
        issues: list[ValidationIssue],
        *,
        help_url: str | None = None,
        message: str = "参数校验失败",
    ) -> None:
        self.issues = issues
        self.help_url = help_url
        self.message = message
        super().__init__(message)

    def as_detail(self) -> dict[str, Any]:
        return {
            "code": "invalid_parameters",
            "message": self.message,
            "errors": [issue.as_dict() for issue in self.issues],
            "help": self.help_url,
        }


@dataclass
class ValidatedParams:
    function: str
    model: str
    values: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    defaults_applied: dict[str, Any] = field(default_factory=dict)


class _CoerceError(ValueError):
    def __init__(self, code: str, message: str, value: Any = None) -> None:
        self.code = code
        self.message = message
        self.value = value
        super().__init__(message)


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    raise _CoerceError("invalid_type", f"需要 bool，收到 {value!r}", value)


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        raise _CoerceError("invalid_type", f"需要整数，收到 {value!r}", value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise _CoerceError("invalid_type", f"需要整数，收到 {value!r}", value)
        return int(value)
    if isinstance(value, str) and _INT_RE.match(value.strip()):
        return int(value.strip())
    raise _CoerceError("invalid_type", f"需要整数，收到 {value!r}", value)


def _to_float(value: Any) -> float:
    if isinstance(value, bool):
        raise _CoerceError("invalid_type", f"需要数字，收到 {value!r}", value)
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        try:
            result = float(value.strip())
        except ValueError as exc:
            raise _CoerceError("invalid_type", f"需要数字，收到 {value!r}", value) from exc
    else:
        raise _CoerceError("invalid_type", f"需要数字，收到 {value!r}", value)
    if not math.isfinite(result):
        raise _CoerceError("invalid_type", f"需要有限数字，收到 {value!r}", value)
    return result


def _coerce(spec: params.ParamSpec, value: Any) -> Any:
    if spec.type == "bool":
        return _to_bool(value)
    if spec.type == "int":
        return _to_int(value)
    if spec.type == "float":
        return _to_float(value)
    if spec.type == "str":
        if not isinstance(value, str):
            raise _CoerceError("invalid_type", f"需要字符串，收到 {value!r}", value)
        return value
    if spec.type == "enum":
        if not isinstance(value, str):
            raise _CoerceError("invalid_type", f"需要字符串，收到 {value!r}", value)
        if spec.enum is None or value not in spec.enum:
            raise _CoerceError(
                "invalid_enum",
                f"必须是 {', '.join(spec.enum or ())} 之一",
                value,
            )
        return value
    return value


def _check_range(spec: params.ParamSpec, value: Any) -> None:
    if spec.type in {"int", "float"} and not isinstance(value, bool):
        if spec.min is not None and value < spec.min:
            raise _CoerceError(
                "out_of_range",
                f"{spec.name} 必须在 {spec.min} 到 {spec.max} 之间",
                value,
            )
        if spec.max is not None and value > spec.max:
            raise _CoerceError(
                "out_of_range",
                f"{spec.name} 必须在 {spec.min} 到 {spec.max} 之间",
                value,
            )


def _validate_segments(value: Any) -> list[dict[str, float]]:
    if not isinstance(value, list):
        raise _CoerceError("invalid_type", "segments 必须是数组", value)
    result: list[dict[str, float]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise _CoerceError("invalid_value", f"segments[{index}] 必须是对象", item)
        try:
            start = _to_float(item.get("start"))
            end = _to_float(item.get("end"))
        except _CoerceError as exc:
            raise _CoerceError(
                "invalid_value", f"segments[{index}] 需要数字 start/end", item
            ) from exc
        if start < 0 or end <= start:
            raise _CoerceError(
                "invalid_value",
                f"segments[{index}] 必须满足 start >= 0 且 end > start",
                item,
            )
        result.append({"start": start, "end": end})
    return result


_VAD_KEYS: dict[str, tuple[float | None, float | None]] = {
    "threshold": (0.0, 1.0),
    "min_speech_duration_ms": (0.0, None),
    "max_speech_duration_s": (0.0, None),
    "min_silence_duration_ms": (0.0, None),
    "speech_pad_ms": (0.0, None),
}


def _validate_vad_parameters(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _CoerceError("invalid_type", "vad_parameters 必须是对象", value)
    result: dict[str, Any] = {}
    for key, raw in value.items():
        if key not in _VAD_KEYS:
            raise _CoerceError("unknown_parameter", f"未知 VAD 参数 {key}", raw)
        number = _to_float(raw)
        minimum, maximum = _VAD_KEYS[key]
        if minimum is not None and number < minimum:
            raise _CoerceError("out_of_range", f"vad_parameters.{key} 不能小于 {minimum}", raw)
        if maximum is not None and number > maximum:
            raise _CoerceError("out_of_range", f"vad_parameters.{key} 不能大于 {maximum}", raw)
        result[key] = number
    return result


def _validate_temperature(value: Any) -> float | list[float]:
    if isinstance(value, (list, tuple)):
        if not value:
            raise _CoerceError("invalid_value", "temperature 数组不能为空", value)
        result = [_to_float(item) for item in value]
        for item in result:
            if item < 0 or item > 2:
                raise _CoerceError("out_of_range", "temperature 必须在 0 到 2 之间", item)
        return result
    number = _to_float(value)
    if number < 0 or number > 2:
        raise _CoerceError("out_of_range", "temperature 必须在 0 到 2 之间", value)
    return number


def _validate_suppress_tokens(value: Any) -> list[int]:
    if not isinstance(value, list):
        raise _CoerceError("invalid_type", "suppress_tokens 必须是数组", value)
    return [_to_int(item) for item in value]


def _validate_clip_timestamps(value: Any) -> str | list[float]:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [_to_float(item) for item in value]
    raise _CoerceError("invalid_type", "clip_timestamps 必须是字符串或数组", value)


def _validate_output_sample_rate(value: Any) -> int:
    number = _to_int(value)
    if number == 0:
        return 0
    if 8000 <= number <= 192000:
        return number
    raise _CoerceError("out_of_range", "output_sample_rate 必须是 0 或 8000 到 192000", value)


_SPECIAL_VALIDATORS = {
    "segments": _validate_segments,
    "vad_parameters": _validate_vad_parameters,
    "temperature": _validate_temperature,
    "suppress_tokens": _validate_suppress_tokens,
    "clip_timestamps": _validate_clip_timestamps,
    "output_sample_rate": _validate_output_sample_rate,
}


def validate(
    function: str,
    model: str | None,
    raw: Mapping[str, Any] | None,
    *,
    default_model: str | None = None,
    strict: bool | None = None,
    help_url: str | None = None,
) -> ValidatedParams:
    if not isinstance(raw, Mapping):
        raise ParamValidationError(
            [ValidationIssue("request", "invalid_type", "请求体必须是 JSON 对象")],
            help_url=help_url,
        )
    provided_raw = dict(raw)

    model_value = model or provided_raw.get("model") or default_model
    try:
        canonical = params.resolve_model(function, str(model_value) if model_value else None)
        params.get_function(function)
        model_spec = params.get_model(function, canonical)
    except ValueError as exc:
        raise ParamValidationError(
            [ValidationIssue("model", "invalid_model", str(exc))],
            help_url=help_url or f"/api/v2/help/{function}",
        ) from exc

    help_url = help_url or f"/api/v2/help/{function}/{canonical}"
    merged = params.merged_params(function, canonical)
    supported = {p.name: p for p in merged}
    alias_to_name: dict[str, str] = {}
    for p in merged:
        for alias in p.aliases:
            alias_to_name[alias] = p.name

    working: dict[str, Any] = {}
    issues: list[ValidationIssue] = []
    for key, value in provided_raw.items():
        if key in alias_to_name:
            target = alias_to_name[key]
            if target in provided_raw:
                issues.append(
                    ValidationIssue(
                        target,
                        "duplicate_parameter",
                        f"参数 {target} 同时以 {key} 和 {target} 出现",
                    )
                )
                continue
            working[target] = value
        else:
            working[key] = value

    strict_value = strict
    if strict_value is None:
        if "strict" in working and working["strict"] is not None:
            try:
                strict_value = _to_bool(working["strict"])
            except _CoerceError as exc:
                issues.append(ValidationIssue("strict", exc.code, exc.message, exc.value))
                strict_value = True
        else:
            strict_value = True

    unknown: list[str] = []
    for key in working:
        if key in model_spec.unsupported:
            issues.append(
                ValidationIssue(
                    key,
                    "unsupported_parameter",
                    f"模型 {canonical} 不支持 {key}：{model_spec.unsupported[key]}",
                )
            )
        elif key not in supported:
            if strict_value:
                issues.append(
                    ValidationIssue(
                        key,
                        "unknown_parameter",
                        f"未知参数 {key}；模型 {canonical} 不支持",
                    )
                )
            else:
                unknown.append(key)

    values: dict[str, Any] = {}
    for p in merged:
        if p.name in working:
            raw_value = working[p.name]
            if raw_value is None:
                continue
            try:
                value = _coerce(p, raw_value)
                _check_range(p, value)
                special = _SPECIAL_VALIDATORS.get(p.name)
                if special is not None:
                    value = special(value)
                values[p.name] = value
            except _CoerceError as exc:
                issues.append(ValidationIssue(p.name, exc.code, exc.message, exc.value))
        elif p.required:
            issues.append(
                ValidationIssue(p.name, "missing_parameter", f"缺少必填参数 {p.name}")
            )

    warnings: list[str] = []
    for key in unknown:
        warnings.append(f"忽略未知参数 {key}")
    defaults_applied: dict[str, Any] = {}
    for p in merged:
        if p.name in values or p.required:
            continue
        default = model_spec.defaults.get(p.name, p.default)
        if default is not None:
            values[p.name] = default
            defaults_applied[p.name] = default

    if "model" in supported:
        values["model"] = canonical

    _validate_cross_fields(
        function,
        canonical,
        model_spec,
        values,
        set(working),
        issues,
        warnings,
    )

    if issues:
        raise ParamValidationError(issues, help_url=help_url)

    return ValidatedParams(
        function=function,
        model=canonical,
        values=values,
        warnings=warnings,
        unknown=unknown,
        defaults_applied=defaults_applied,
    )


def _validate_cross_fields(
    function: str,
    model: str,
    model_spec: params.ModelSpec,
    values: dict[str, Any],
    provided: set[str],
    issues: list[ValidationIssue],
    warnings: list[str],
) -> None:
    if function == "tts":
        if "target_lufs" in provided and not values.get("normalize_loudness"):
            warnings.append("target_lufs 只在 normalize_loudness=true 时生效")
        return

    if function == "asr":
        if model_spec.kind == "qwen" and values.get("task") == "translate":
            issues.append(
                ValidationIssue(
                    "task",
                    "invalid_value",
                    "Qwen3-ASR 不支持 task=translate；请使用 large-v3",
                    "translate",
                )
            )
        hotwords = values.get("hotwords")
        prefix = values.get("prefix")
        if isinstance(hotwords, str) and hotwords.strip() and isinstance(prefix, str) and prefix.strip():
            issues.append(
                ValidationIssue(
                    "hotwords",
                    "conflict_parameter",
                    "hotwords 与 prefix 不能同时使用",
                )
            )
        if "vad_parameters" in provided and not values.get("vad_filter"):
            warnings.append("vad_parameters 只在 vad_filter=true 时生效")
        if (
            "language_detection_threshold" in provided
            or "language_detection_segments" in provided
        ) and values.get("language"):
            warnings.append("language_detection_* 只在 language 为空时生效")
        return

    if function == "vc":
        segments = values.get("segments")
        if values.get("convert_all") and segments:
            issues.append(
                ValidationIssue(
                    "convert_all",
                    "conflict_parameter",
                    "convert_all=true 时不能同时传 segments",
                )
            )
        ref_duration = values.get("ref_duration")
        if (
            isinstance(ref_duration, float)
            and ref_duration > 0
            and model_spec.ref_max_len is not None
            and ref_duration > model_spec.ref_max_len
        ):
            values["ref_duration"] = model_spec.ref_max_len
            warnings.append(
                f"ref_duration 超过模型上限，已截断为 {model_spec.ref_max_len:g} 秒"
            )
        if isinstance(values.get("length_adjust"), float) and values["length_adjust"] != 1.0:
            warnings.append("length_adjust != 1.0 会改变时间轴")
        if "target_lufs" in provided and not values.get("normalize_loudness"):
            warnings.append("target_lufs 只在 normalize_loudness=true 时生效")
