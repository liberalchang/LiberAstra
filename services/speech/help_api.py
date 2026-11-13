"""从参数注册表生成 Help / 模型目录 JSON。"""

from __future__ import annotations

import os
from importlib import metadata
from typing import Any

import params

SCHEMA_VERSION = "1.0"
_ALLOWED_INCLUDE = {"common", "model", "defaults", "examples", "errors", "unsupported"}
ERROR_CODES: dict[str, str] = {
    "missing_parameter": "缺少必填参数",
    "invalid_type": "参数类型不正确",
    "out_of_range": "参数超出允许范围",
    "invalid_enum": "参数值不在枚举内",
    "unknown_parameter": "未知参数",
    "unsupported_parameter": "当前模型不支持该参数",
    "duplicate_parameter": "参数重复传入",
    "conflict_parameter": "互斥参数同时出现",
    "invalid_value": "参数值不合法",
    "invalid_model": "模型不存在或不受支持",
    "invalid_file_id": "文件 ID 格式不合法",
    "file_not_found": "文件不存在",
    "file_expired": "文件已过期",
    "empty_file": "上传文件为空",
    "upload_limit_exceeded": "超过运维配置的上传上限",
    "decoder_unsupported": "无法解码输入媒体",
    "model_limit_exceeded": "超过模型能力上限",
    "resource_exhausted": "显存或磁盘资源不足",
    "synthesis_failed": "语音合成失败",
    "transcription_failed": "语音识别失败",
    "conversion_failed": "换音失败",
    "ffmpeg_failed": "音频后处理失败",
    "timeout": "请求超时",
    "internal_error": "内部错误",
}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _include_set(include: str | list[str] | None) -> set[str] | None:
    if include is None:
        return None
    values = include if isinstance(include, list) else str(include).split(",")
    result = {str(item).strip() for item in values if str(item).strip()}
    unknown = result - _ALLOWED_INCLUDE
    if unknown:
        raise ValueError(
            f"未知 include 值 {', '.join(sorted(unknown))}；可选 {', '.join(sorted(_ALLOWED_INCLUDE))}"
        )
    return result or None


def _runtime_version(package: str) -> str | None:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def runtime_versions() -> dict[str, str | None]:
    return {
        "chatterbox-tts": _runtime_version("chatterbox-tts"),
        "faster-whisper": _runtime_version("faster-whisper"),
        "qwen-asr": _runtime_version("qwen-asr"),
    }


def service_limits() -> dict[str, Any]:
    max_upload = _env_int("LIBER_SPEECH_MAX_UPLOAD_BYTES", 0)
    max_media = _env_int("LIBER_SPEECH_MAX_MEDIA_SECONDS", 0)
    return {
        "max_upload_bytes": max_upload,
        "max_media_seconds": max_media,
        "file_ttl_seconds": _env_int("LIBER_SPEECH_FILE_TTL_SECONDS", 86400),
        "unlimited": max_upload == 0 and max_media == 0,
    }


def _param_payload(function: str, model: str, p: params.ParamSpec) -> dict[str, Any]:
    return {
        "name": p.name,
        "type": p.type,
        "required": p.required,
        "default": params.effective_default(function, model, p.name),
        "min": p.min,
        "max": p.max,
        "enum": list(p.enum) if p.enum else None,
        "description": p.description,
        "advanced": p.advanced,
        "scope": p.scope,
        "supported": True,
    }


def _model_limits(function: str, model: str, spec: params.ModelSpec) -> dict[str, Any]:
    limits: dict[str, Any] = {}
    if spec.ref_max_len is not None:
        limits["ref_audio_seconds"] = spec.ref_max_len
    if function == "asr" and spec.kind == "qwen":
        limits["max_new_tokens"] = params.effective_default(function, model, "max_new_tokens")
        limits["max_inference_batch_size"] = params.effective_default(
            function, model, "max_inference_batch_size"
        )
    return limits


def _unsupported_payload(function: str, model: str) -> list[dict[str, str]]:
    return [
        {"name": name, "reason": reason}
        for name, reason in params.unsupported_params(function, model).items()
    ]


def _model_summary(function: str, model: str) -> dict[str, Any]:
    spec = params.get_model(function, model)
    merged = params.merged_params(function, model)
    return {
        "id": spec.id,
        "label": spec.label,
        "kind": spec.kind,
        "params_url": f"/api/v2/help/{function}/{spec.id}",
        "supports": [p.name for p in merged],
        "unsupported": list(spec.unsupported),
        "limits": _model_limits(function, spec.id, spec),
        "notes": list(spec.notes),
    }


def _examples(function: str, model: str) -> dict[str, Any]:
    if function == "tts":
        body: dict[str, Any] = {
            "text": "你好，欢迎使用。",
            "model": model,
            "language": "zh",
            "format": "wav",
            "strict": True,
        }
    elif function == "asr":
        body = {
            "file_id": "f_input",
            "model": model,
            "language": "zh",
            "task": "transcribe",
            "timestamps": "segment",
            "strict": True,
        }
    else:
        body = {
            "file_id": "f_input",
            "prompt_file_id": "f_ref",
            "model": model,
            "strict": True,
        }
    return {"path": params.get_function(function).endpoint, "body": body}


def _filter_params(
    function: str,
    model: str,
    include: set[str] | None,
) -> list[params.ParamSpec]:
    merged = params.merged_params(function, model)
    if not include:
        return list(merged)
    if not ({"common", "model"} & include):
        return list(merged)
    selected: set[str] = set()
    if "common" in include:
        selected.update(p.name for p in merged if p.models is None)
    if "model" in include:
        selected.update(p.name for p in merged if p.models is not None)
    return [p for p in merged if p.name in selected]


def _model_payload(
    function: str,
    model: str,
    include: set[str] | None,
) -> dict[str, Any]:
    canonical = params.resolve_model(function, model)
    spec = params.get_model(function, canonical)
    function_spec = params.get_function(function)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "function": function,
        "model": canonical,
        "endpoint": {
            "method": "POST",
            "path": function_spec.endpoint,
            "content_type": function_spec.content_type,
        },
        "model_info": {
            "id": spec.id,
            "label": spec.label,
            "kind": spec.kind,
            "notes": list(spec.notes),
        },
        "parameters": [
            _param_payload(function, canonical, p)
            for p in _filter_params(function, canonical, include)
        ],
        "model_limits": _model_limits(function, canonical, spec),
        "service_limits": service_limits(),
        "notes": list(function_spec.notes),
        "runtime_versions": runtime_versions(),
    }
    if include is None or "unsupported" in include:
        payload["unsupported_parameters"] = _unsupported_payload(function, canonical)
    if include is None or "examples" in include:
        payload["examples"] = _examples(function, canonical)
    if include is None or "errors" in include:
        payload["error_codes"] = ERROR_CODES
    return payload


def _function_payload(function: str, include: set[str] | None) -> dict[str, Any]:
    spec = params.get_function(function)
    common = [p for p in spec.params if p.models is None]
    first_model = next(iter(spec.models))
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "function": function,
        "endpoint": {
            "method": "POST",
            "path": spec.endpoint,
            "content_type": spec.content_type,
        },
        "common_parameters": [
            _param_payload(function, first_model, p) for p in common
        ],
        "models": [_model_summary(function, model_id) for model_id in spec.models],
        "notes": list(spec.notes),
        "service_limits": service_limits(),
        "runtime_versions": runtime_versions(),
    }
    if include is not None and "errors" in include:
        payload["error_codes"] = ERROR_CODES
    return payload


def build_help(
    function: str | None = None,
    model: str | None = None,
    include: str | list[str] | None = None,
) -> dict[str, Any]:
    include_set = _include_set(include)
    if function is None:
        if model:
            raise ValueError("指定 model 时必须同时指定 function")
        return {
            "schema_version": SCHEMA_VERSION,
            "service": "Liber Speech",
            "functions": {
                name: {
                    "endpoint": {
                        "method": "POST",
                        "path": spec.endpoint,
                        "content_type": spec.content_type,
                    },
                    "params_url": f"/api/v2/help/{name}",
                    "models": [
                        {"id": model_id, "label": model_spec.label}
                        for model_id, model_spec in spec.models.items()
                    ],
                }
                for name, spec in params.FUNCTIONS.items()
            },
            "default_models": {
                "tts": os.getenv("LIBER_SPEECH_TTS_MODEL", "multilingual_v3"),
                "asr": os.getenv("LIBER_SPEECH_ASR_MODEL", "large-v3"),
                "vc": os.getenv("LIBER_SPEECH_VC_MODEL", "chatterbox"),
            },
            "service_limits": service_limits(),
            "runtime_versions": runtime_versions(),
            "error_codes": ERROR_CODES,
        }
    if model:
        return _model_payload(function, model, include_set)
    return _function_payload(function, include_set)


def build_models() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "models": {
            name: [_model_summary(name, model_id) for model_id in spec.models]
            for name, spec in params.FUNCTIONS.items()
        },
        "default_models": {
            "tts": os.getenv("LIBER_SPEECH_TTS_MODEL", "multilingual_v3"),
            "asr": os.getenv("LIBER_SPEECH_ASR_MODEL", "large-v3"),
            "vc": os.getenv("LIBER_SPEECH_VC_MODEL", "chatterbox"),
        },
        "service_limits": service_limits(),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    if "functions" in payload:
        lines.append("# Liber Speech Help")
        for name, item in payload["functions"].items():
            lines.append(f"## {name}")
            lines.append(f"- 端点：`{item['endpoint']['path']}`")
            lines.append(f"- 模型：{', '.join(model['id'] for model in item['models'])}")
        return "\n".join(lines) + "\n"
    if "model" in payload:
        lines.append(f"# {payload['function']} / {payload['model']}")
        lines.append(f"- 端点：`{payload['endpoint']['path']}`")
        lines.append("")
        lines.append("## 参数")
        for item in payload.get("parameters", []):
            default = item.get("default")
            lines.append(
                f"- `{item['name']}` ({item['type']}, 默认 {default!r}): {item['description']}"
            )
        unsupported = payload.get("unsupported_parameters") or []
        if unsupported:
            lines.append("")
            lines.append("## 不支持的参数")
            for item in unsupported:
                lines.append(f"- `{item['name']}`: {item['reason']}")
        return "\n".join(lines) + "\n"
    lines.append(f"# {payload.get('function', 'help')}")
    for item in payload.get("common_parameters", []):
        lines.append(f"- `{item['name']}` ({item['type']}): {item['description']}")
    return "\n".join(lines) + "\n"
