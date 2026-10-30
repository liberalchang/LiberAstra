"""供应商分组、模型目录与画布菜单出厂项。

模型条目存在 Provider.extra["model_catalog"]。Provider.models 仍只保存已启用的模型 ID，
旧接口继续读这个字符串列表。
"""

from __future__ import annotations

from typing import Any

# 服务提供方页面的两大类。其余已注册类型归入 api，避免旧 Provider 从列表消失。
LOCAL_TYPES = ("comfyui", "ollama", "liber_speech", "edge_tts")
API_TYPES = ("volcengine_ark", "volcengine_speech", "openai_compatible")

PROVIDER_GROUP = {
    "comfyui": "local",
    "ollama": "local",
    "liber_speech": "local",
    "edge_tts": "local",
    "volcengine_ark": "api",
    "volcengine_speech": "api",
    "openai_compatible": "api",
    "anthropic": "api",
    "google": "api",
    "openai": "api",
    "chatgpt": "api",
    "deepseek": "api",
    "kimi_code": "api",
    "aliyun_bailian": "api",
    "openai_tts": "api",
    "openai_stt": "api",
    "openai_images": "api",
}

# 模型目录不收录工作流包专属能力。那些包由画布菜单单独匹配。
_WORKFLOW_ONLY_SUBS = frozenset(
    {"color_grade", "inpaint", "outfit_swap", "depth_pose", "depth_gen", "i2v_orbit"}
)

_LLM_PROVIDER_TYPES = (
    "ollama",
    "openai_compatible",
    "anthropic",
    "google",
    "openai",
    "chatgpt",
    "deepseek",
    "kimi_code",
    "aliyun_bailian",
)


def _param_field(key: str, spec: dict[str, Any], *, when_sub: str = "") -> dict[str, Any]:
    """把执行器字段收成设置页白名单。只保留表单需要的键。"""
    row: dict[str, Any] = {"key": key, "type": spec["type"], "label": spec["label"]}
    if "default" in spec:
        row["default"] = spec["default"]
    if spec.get("options"):
        row["options"] = list(spec["options"])
    if "min" in spec:
        row["min"] = spec["min"]
    if "max" in spec:
        row["max"] = spec["max"]
    if when_sub:
        row["when_sub"] = when_sub
    return row


def _llm_param_schema() -> list[dict[str, Any]]:
    return [{"key": "max_output", "type": "int", "label": "最大输出 Token", "min": 1, "max": 200_000}]


def _ark_param_schemas() -> dict[str, list[dict[str, Any]]]:
    """方舟图像、视频参数与请求体共用同一份字段，种子只留在画布节点。"""
    from liberastra.providers.vendors.volcengine.schemas import IMAGE_FIELDS, VIDEO_FIELDS

    image = [_param_field(key, spec) for key, spec in IMAGE_FIELDS.items()]
    image.append(
        _param_field(
            "sequential_image_generation",
            {"type": "str", "label": "组图", "default": "disabled", "options": ["disabled", "auto"]},
            when_sub="t2i",
        )
    )
    video = [_param_field(key, spec) for key, spec in VIDEO_FIELDS.items() if key != "seed"]
    return {"llm": _llm_param_schema(), "image": image, "video": video}


def model_profile(provider_type: str) -> dict[str, Any]:
    """这个服务商在模型设置里能选的类型、能力和会转发的参数。"""
    if provider_type in _LLM_PROVIDER_TYPES:
        return {
            "model_kinds": ["llm"],
            "sub_capabilities_by_kind": {"llm": ["chat", "vision"]},
            "param_schemas": {"llm": _llm_param_schema()},
        }
    if provider_type == "volcengine_ark":
        return {
            "model_kinds": ["llm", "image", "video"],
            "sub_capabilities_by_kind": {
                "llm": ["chat", "vision"],
                "image": ["t2i", "i2i_single", "i2i_multi"],
                "video": ["t2v", "i2v_first", "i2v_flf", "v2v_ref"],
            },
            "param_schemas": _ark_param_schemas(),
        }
    if provider_type in {"volcengine_speech", "liber_speech"}:
        return {
            "model_kinds": ["speech"],
            "sub_capabilities_by_kind": {"speech": ["tts", "asr"]},
            "param_schemas": {},
        }
    if provider_type in {"edge_tts", "openai_tts"}:
        return {
            "model_kinds": ["speech"],
            "sub_capabilities_by_kind": {"speech": ["tts"]},
            "param_schemas": {},
        }
    if provider_type == "openai_stt":
        return {
            "model_kinds": ["speech"],
            "sub_capabilities_by_kind": {"speech": ["asr"]},
            "param_schemas": {},
        }
    if provider_type == "openai_images":
        return {
            "model_kinds": ["image"],
            "sub_capabilities_by_kind": {"image": ["t2i"]},
            "param_schemas": {},
        }
    return {"model_kinds": [], "sub_capabilities_by_kind": {}, "param_schemas": {}}


def execution_fields(provider_type: str, sub_capability: str) -> dict[str, dict[str, Any]]:
    """画布节点上的参数。只有适配器真会读的服务商才有字段。"""
    if provider_type != "volcengine_ark":
        return {}
    from liberastra.providers.vendors.volcengine.schemas import fields_for

    return fields_for(sub_capability)


# 细分能力 → 画布菜单大类、展示名、媒体槽。
# 槽位决定功能页上传框和画布自动补建的前置节点。
SUB_CAPABILITIES: dict[str, dict[str, Any]] = {
    "chat": {"menu": "speech", "category": "llm", "label": "对话", "slots": []},
    "vision": {"menu": "image", "category": "llm", "label": "视觉理解", "slots": []},
    "t2i": {
        "menu": "image",
        "category": "image",
        "label": "文生图",
        "slots": [{"key": "prompt", "type": "text", "label": "提示词", "required": True}],
    },
    "i2i_single": {
        "menu": "image",
        "category": "image",
        "label": "单图编辑",
        "slots": [{"key": "image", "type": "image", "label": "参考图片", "required": True}],
    },
    "i2i_multi": {
        "menu": "image",
        "category": "image",
        "label": "多图编辑",
        "slots": [
            {
                "key": "image",
                "type": "image",
                "label": "参考图片",
                "required": True,
                "multiple": True,
            }
        ],
    },
    "inpaint": {
        "menu": "image",
        "category": "image",
        "label": "蒙版",
        "slots": [
            {"key": "image", "type": "image", "label": "原图", "required": True},
            {"key": "mask", "type": "image", "label": "蒙版", "required": True},
        ],
    },
    "outfit_swap": {
        "menu": "image",
        "category": "image",
        "label": "换衣",
        "slots": [
            {"key": "image", "type": "image", "label": "人物照", "required": True},
            {"key": "image_2", "type": "image", "label": "衣服图", "required": True},
        ],
    },
    "depth_pose": {
        "menu": "image",
        "category": "image",
        "label": "深度换姿",
        "slots": [
            {"key": "image", "type": "image", "label": "人物照", "required": True},
            {"key": "image_2", "type": "image", "label": "深度图", "required": True},
        ],
    },
    "depth_gen": {
        "menu": "image",
        "category": "image",
        "label": "深度生图",
        "slots": [{"key": "image", "type": "image", "label": "深度图", "required": True}],
    },
    "color_grade": {
        "menu": "image",
        "category": "image",
        "label": "调色",
        "slots": [
            {"key": "image", "type": "image", "label": "原图", "required": True},
            {"key": "image_2", "type": "image", "label": "调色参考", "required": True},
        ],
    },
    "upscale": {
        "menu": "image",
        "category": "image",
        "label": "放大修复",
        "slots": [{"key": "image", "type": "image", "label": "原图", "required": True}],
    },
    "analysis": {
        "menu": "image",
        "category": "llm",
        "label": "画面分析",
        "slots": [{"key": "image", "type": "image", "label": "画面", "required": True}],
    },
    "video_analysis": {
        "menu": "video",
        "category": "llm",
        "label": "视频分析",
        "slots": [{"key": "video", "type": "video", "label": "视频", "required": True}],
    },
    "t2v": {
        "menu": "video",
        "category": "video",
        "label": "文生视频",
        "slots": [{"key": "prompt", "type": "text", "label": "提示词", "required": True}],
    },
    "t2v_enhance": {
        "menu": "video",
        "category": "video",
        "label": "文生增强",
        "slots": [{"key": "prompt", "type": "text", "label": "提示词", "required": True}],
    },
    "i2v_first": {
        "menu": "video",
        "category": "video",
        "label": "首帧生视频",
        "slots": [{"key": "first_frame", "type": "image", "label": "首帧图片", "required": True}],
    },
    "i2v_flf": {
        "menu": "video",
        "category": "video",
        "label": "首尾帧视频",
        "slots": [
            {"key": "first_frame", "type": "image", "label": "首帧图片", "required": True},
            {"key": "last_frame", "type": "image", "label": "尾帧图片", "required": True},
        ],
    },
    "i2v_orbit": {
        "menu": "video",
        "category": "video",
        "label": "360全景",
        "slots": [
            {"key": "image", "type": "image", "label": "首帧图片", "required": True},
            {"key": "image_2", "type": "image", "label": "结束画面", "required": False},
        ],
    },
    "i2v_enhance": {
        "menu": "video",
        "category": "video",
        "label": "图生增强",
        "slots": [{"key": "image", "type": "image", "label": "首帧图片", "required": True}],
    },
    "v2v_ref": {
        "menu": "video",
        "category": "video",
        "label": "参考生视频",
        "slots": [
            {
                "key": "reference_image",
                "type": "image",
                "label": "参考图片",
                "required": False,
                "multiple": True,
            },
            {
                "key": "reference_video",
                "type": "video",
                "label": "参考视频",
                "required": False,
            },
            {
                "key": "reference_audio",
                "type": "audio",
                "label": "参考音频",
                "required": False,
            },
        ],
    },
    "avatar": {
        "menu": "video",
        "category": "video",
        "label": "数字人口播",
        "slots": [
            {"key": "image", "type": "image", "label": "人物图片", "required": True},
            {"key": "audio", "type": "audio", "label": "口播音频", "required": True},
        ],
    },
    "motion": {
        "menu": "video",
        "category": "video",
        "label": "动作迁移",
        "slots": [
            {"key": "image", "type": "image", "label": "人物图片", "required": True},
            {"key": "video", "type": "video", "label": "动作视频", "required": True},
        ],
    },
    "tts": {"menu": "speech", "category": "tts", "label": "文字转语音", "slots": []},
    "asr": {
        "menu": "speech",
        "category": "asr",
        "label": "语音识别",
        "slots": [{"key": "audio", "type": "audio", "label": "音频", "required": True}],
    },
}

# 工作流包的粗能力落到一个默认细分能力。包名里的 ref / 多图会再细分。
PACK_CAPABILITY_SUB = {
    "t2i": "t2i",
    "i2i": "i2i_single",
    "upscale": "upscale",
    "t2v": "t2v",
    "i2v": "i2v_first",
    "avatar": "avatar",
    "motion": "motion",
    "analysis": "analysis",
    "tts": "tts",
}


def provider_group(provider_type: str) -> str:
    return PROVIDER_GROUP.get(provider_type, "api")


def media_slots(sub_capability: str) -> list[dict[str, Any]]:
    spec = SUB_CAPABILITIES.get(sub_capability) or {}
    slots = []
    for raw in spec.get("slots") or []:
        slots.append(
            {
                "key": raw["key"],
                "type": raw["type"],
                "label": raw["label"],
                "required": bool(raw.get("required", True)),
                "multiple": bool(raw.get("multiple", False)),
                "input_kind": raw.get("input_kind") or raw["type"],
            }
        )
    # 云端模型的生成能力都要提示词。工作流是否补文本由 manifest 的 required 决定，不走这里。
    prompt_functions = {
        "t2i",
        "t2v",
        "t2v_enhance",
        "i2i_single",
        "i2i_multi",
        "inpaint",
        "i2v_first",
        "i2v_flf",
        "i2v_enhance",
        "v2v_ref",
        "tts",
    }
    if sub_capability in prompt_functions and not any(slot["type"] == "text" for slot in slots):
        slots.append(
            {
                "key": "prompt",
                "type": "text",
                "label": "提示词",
                "required": True,
                "multiple": False,
                "input_kind": "text",
            }
        )
    if sub_capability == "motion":
        for slot in slots:
            if slot["type"] == "image" and slot["required"]:
                slot["input_kind"] = "character"
    return slots


# 模型设置里能保存、并且执行器会读取的默认参数。
_DEFAULT_KEYS = {
    "size",
    "output_format",
    "watermark",
    "sequential_image_generation",
    "resolution",
    "ratio",
    "duration",
    "generate_audio",
    "camera_fixed",
}
_BOOL_DEFAULTS = {"watermark", "generate_audio", "camera_fixed"}


def model_item(
    model_id: str,
    *,
    label: str,
    category: str,
    sub_capabilities: list[str],
    enabled: bool = True,
    custom: bool = False,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = {
        "id": model_id,
        "label": label,
        "category": category,
        "sub_capabilities": list(sub_capabilities),
        "enabled": enabled,
        "custom": custom,
    }
    if params:
        item["params"] = params
    return item


def _kind_for_category(category: str) -> str:
    if category in {"tts", "asr"}:
        return "speech"
    return category


def _clean_against_schema(raw: Any, schema: list[dict[str, Any]]) -> dict[str, Any]:
    """按这一类型的白名单收参数。没登记的键丢掉。"""
    if not isinstance(raw, dict) or not schema:
        return {}
    by_key = {str(field["key"]): field for field in schema}
    cleaned: dict[str, Any] = {}
    defaults: dict[str, Any] = {}
    incoming = raw.get("defaults") if isinstance(raw.get("defaults"), dict) else {}
    max_output = raw.get("max_output")
    for key, field in by_key.items():
        value = max_output if key == "max_output" else incoming.get(key)
        if value in (None, ""):
            continue
        kind = field["type"]
        if kind == "int":
            try:
                number = int(value)
            except (TypeError, ValueError):
                continue
            low = int(field.get("min", number))
            high = int(field.get("max", number))
            number = max(low, min(high, number))
            if key == "max_output":
                cleaned["max_output"] = number
            else:
                defaults[key] = number
        elif kind == "bool":
            if isinstance(value, str):
                defaults[key] = value.strip().lower() in {"1", "true", "yes", "on"}
            else:
                defaults[key] = bool(value)
        else:
            text = str(value)[:32]
            options = field.get("options")
            if options and text not in options:
                continue
            defaults[key] = text
    if defaults:
        cleaned["defaults"] = defaults
    return cleaned


def clean_model_params(raw: Any, schema: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """只保留对话的最大输出，以及图像、视频执行器认识的默认值。"""
    if schema is not None:
        return _clean_against_schema(raw, schema)
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, Any] = {}
    max_output = raw.get("max_output")
    if max_output not in (None, ""):
        try:
            tokens = int(max_output)
        except (TypeError, ValueError):
            tokens = 0
        if 1 <= tokens <= 200_000:
            cleaned["max_output"] = tokens
    defaults_raw = raw.get("defaults")
    defaults: dict[str, Any] = {}
    if isinstance(defaults_raw, dict):
        for key, value in defaults_raw.items():
            if key not in _DEFAULT_KEYS or value in (None, ""):
                continue
            if key in _BOOL_DEFAULTS:
                if isinstance(value, str):
                    defaults[key] = value.strip().lower() in {"1", "true", "yes", "on"}
                else:
                    defaults[key] = bool(value)
            elif key == "duration":
                try:
                    defaults[key] = max(-1, min(30, int(value)))
                except (TypeError, ValueError):
                    continue
            else:
                defaults[key] = str(value)[:32]
    if defaults:
        cleaned["defaults"] = defaults
    return cleaned


def normalize_model_item(raw: dict[str, Any], *, provider_type: str = "") -> dict[str, Any]:
    """把用户提交或历史记录收成固定字段。未知细分能力丢掉。"""
    model_id = str(raw.get("id") or "").strip()
    if not model_id:
        raise ValueError("模型 ID 不能为空")
    subs = [
        str(item)
        for item in (raw.get("sub_capabilities") or [])
        if str(item) in SUB_CAPABILITIES and str(item) not in _WORKFLOW_ONLY_SUBS
    ]
    category = str(raw.get("category") or "")
    if category == "unknown":
        subs = []
    elif category not in {"llm", "image", "video", "tts", "asr"}:
        category = _category_from_subs(subs) or "llm"
    if provider_type:
        profile = model_profile(provider_type)
        kind = _kind_for_category(category)
        if category != "unknown" and kind not in profile["model_kinds"]:
            category = "unknown"
            subs = []
        elif category != "unknown":
            allowed = set(profile["sub_capabilities_by_kind"].get(kind, []))
            if category in {"tts", "asr"}:
                allowed &= {category}
            subs = [item for item in subs if item in allowed]
        schema = [] if category == "unknown" else profile["param_schemas"].get(kind, [])
        params = {} if category == "unknown" else clean_model_params(raw.get("params"), schema)
    else:
        params = clean_model_params(raw.get("params"))
        if category == "unknown":
            params = {}
        elif category == "llm":
            params.pop("defaults", None)
        elif category in {"image", "video"}:
            params.pop("max_output", None)
        else:
            params = {}
    label = str(raw.get("label") or "").strip() or model_id
    return model_item(
        model_id,
        label=label[:80],
        category=category,
        sub_capabilities=subs,
        enabled=bool(raw.get("enabled", True)),
        custom=bool(raw.get("custom", False)),
        params=params,
    )


def _category_from_subs(subs: list[str]) -> str:
    for sub in subs:
        category = str((SUB_CAPABILITIES.get(sub) or {}).get("category") or "")
        if category in {"llm", "image", "video", "tts", "asr"}:
            return category
    return ""


def resolve_model_capabilities(provider_type: str, model_id: str) -> list[str]:
    """按厂商能力表精确匹配。表里没有的模型不进入任何功能，交给用户勾选。"""
    from liberastra.providers.vendors.volcengine.presets import presets_for

    for item in presets_for(provider_type):
        if item["id"] == model_id:
            return list(item["sub_capabilities"])
    return []


# 按服务商类型归类。对话类服务商里，嵌入和重排模型不标成对话。
_NON_CHAT_TOKENS = ("bge", "embed", "rerank", "e5-", "e5_", "minilm", "whisper")


def non_generative_model(model_id: str) -> bool:
    """名字能确定不是对话模型。不据此猜测文生图或视频。"""
    folded = model_id.lower().replace(" ", "")
    return any(token in folded for token in _NON_CHAT_TOKENS)
_PROVIDER_KIND: dict[str, tuple[str, list[str]]] = {
    "ollama": ("llm", ["chat"]),
    "openai_compatible": ("llm", ["chat"]),
    "anthropic": ("llm", ["chat"]),
    "google": ("llm", ["chat"]),
    "openai": ("llm", ["chat"]),
    "chatgpt": ("llm", ["chat"]),
    "deepseek": ("llm", ["chat"]),
    "kimi_code": ("llm", ["chat"]),
    "aliyun_bailian": ("llm", ["chat"]),
    "edge_tts": ("tts", ["tts"]),
    "openai_tts": ("tts", ["tts"]),
    "openai_stt": ("asr", ["asr"]),
    "openai_images": ("image", ["t2i"]),
}


def classify_remote(provider_type: str, model_id: str) -> dict[str, Any] | None:
    """远端或历史 models 列表收成目录项。ComfyUI 检查点不猜能力，留在全部。"""
    name = model_id.strip()
    if not name:
        return None
    if provider_type == "liber_speech":
        upper = name.upper()
        if upper.endswith("ASR") or "· ASR" in upper:
            return model_item(name, label=name, category="asr", sub_capabilities=["asr"], enabled=False)
        if upper.endswith("TTS") or "· TTS" in upper:
            return model_item(name, label=name, category="tts", sub_capabilities=["tts"], enabled=False)
        return classify_model_id(name)
    kind = _PROVIDER_KIND.get(provider_type)
    if kind is None:
        return classify_model_id(name)
    category, subs = kind
    if subs == ["chat"] and non_generative_model(name):
        return classify_model_id(name)
    return model_item(name, label=name, category=category, sub_capabilities=subs, enabled=False)


def classify_model_id(model_id: str) -> dict[str, Any] | None:
    """远端列表里不认识的模型。不按名字猜测它能做文生图还是视频。"""
    name = model_id.strip()
    if not name:
        return None
    return model_item(
        name,
        label=name,
        category="unknown",
        sub_capabilities=[],
        enabled=False,
    )


def merge_catalog(
    existing: list[dict[str, Any]] | None,
    remote_ids: list[str],
    presets: list[dict[str, Any]],
    *,
    provider_type: str = "",
) -> list[dict[str, Any]]:
    """预设表 + 远端列表 + 用户已有开关。手动添加的接入点始终保留。"""
    by_id: dict[str, dict[str, Any]] = {}
    for preset in presets:
        item = normalize_model_item(preset, provider_type=provider_type)
        by_id[item["id"]] = item
    for raw in existing or []:
        try:
            item = normalize_model_item(raw, provider_type=provider_type)
        except ValueError:
            continue
        previous = by_id.get(item["id"])
        if previous is None:
            by_id[item["id"]] = item
            continue
        # 用户改过的简称、开关和手动能力优先于预设。
        previous["enabled"] = item["enabled"]
        previous["custom"] = item["custom"] or previous["custom"]
        if item["custom"] or item["label"] != item["id"]:
            previous["label"] = item["label"]
        if item["custom"]:
            previous["sub_capabilities"] = item["sub_capabilities"]
            previous["category"] = item["category"]
            previous.pop("params", None)
        if item.get("params"):
            previous["params"] = item["params"]
    for remote_id in remote_ids:
        if remote_id in by_id:
            continue
        guessed = classify_remote(provider_type, remote_id) if provider_type else classify_model_id(remote_id)
        if guessed is not None:
            by_id[remote_id] = normalize_model_item(guessed, provider_type=provider_type)
    return sorted(by_id.values(), key=lambda item: (not item["custom"], item["id"]))


def enabled_model_ids(catalog: list[dict[str, Any]]) -> list[str]:
    return [str(item["id"]) for item in catalog if item.get("enabled")]


def read_catalog(extra: dict[str, Any] | None, provider_type: str = "") -> list[dict[str, Any]]:
    raw = (extra or {}).get("model_catalog")
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in raw:
        if isinstance(entry, dict):
            try:
                items.append(normalize_model_item(entry, provider_type=provider_type))
            except ValueError:
                continue
    return items


def pack_sub_capability(name: str, capability: str, image_input_count: int) -> str:
    """按包名里的用途区分功能。粗能力只作兜底，避免环绕和调色被并进别的功能。"""
    lowered = name.lower()
    if "color_grade" in lowered:
        return "color_grade"
    if "inpaint" in lowered:
        return "inpaint"
    if "outfit_swap" in lowered:
        return "outfit_swap"
    if "union_depth" in lowered:
        return "depth_gen"
    if "union_" in lowered:
        return "depth_pose"
    if "_orbit" in lowered:
        return "i2v_orbit"
    if "enhancer" in lowered and capability == "i2v":
        return "i2v_enhance"
    if "enhancer" in lowered and capability == "t2v":
        return "t2v_enhance"
    if capability == "analysis" and "video" in lowered:
        return "video_analysis"
    if capability == "i2v" and "ref" in lowered:
        return "v2v_ref"
    if capability == "i2i" and ("multi" in lowered or image_input_count >= 2):
        return "i2i_multi"
    if capability == "i2v" and image_input_count >= 2:
        return "i2v_flf"
    return PACK_CAPABILITY_SUB.get(capability, capability)


def targets_for_menu_item(item: dict[str, Any], specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """自动模式返回该能力的全部目标。手动模式只返回勾选过的目标。"""
    sub = item.get("sub_capability")
    pool = [spec for spec in specs if spec.get("sub_capability") == sub]
    if item.get("bind_mode") != "manual":
        return pool
    chosen: list[dict[str, Any]] = []
    for spec in pool:
        for target in item.get("manual_targets") or []:
            if not isinstance(target, dict):
                continue
            same = (
                target.get("target_id") == spec.get("target_id")
                and target.get("target_type") == spec.get("target_type")
            )
            provider_id = target.get("provider_id")
            if same and (not provider_id or provider_id == spec.get("provider_id")):
                chosen.append(spec)
                break
    return chosen


# 图像和视频菜单按最小功能列出。同一功能的官方版、越狱版以及同功能的其他包进同一项。
# 没有对应工作流的能力（如首尾帧）不出现；语音没有工作流包，仍自动匹配模型。
_WORKFLOW_MENU_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("preset_t2i", "image", "文生图", "t2i"),
    ("preset_i2i", "image", "单图编辑", "i2i_single"),
    ("preset_i2i_multi", "image", "多图编辑", "i2i_multi"),
    ("preset_outfit", "image", "换衣", "outfit_swap"),
    ("preset_depth_pose", "image", "深度换姿", "depth_pose"),
    ("preset_depth_gen", "image", "深度生图", "depth_gen"),
    ("preset_color_grade", "image", "调色", "color_grade"),
    ("preset_inpaint", "image", "蒙版", "inpaint"),
    ("preset_upscale", "image", "放大修复", "upscale"),
    ("preset_analysis", "image", "画面分析", "analysis"),
    ("preset_t2v", "video", "文生视频", "t2v"),
    ("preset_t2v_enhance", "video", "文生增强", "t2v_enhance"),
    ("preset_i2v_first", "video", "图生视频", "i2v_first"),
    ("preset_i2v_enhance", "video", "图生增强", "i2v_enhance"),
    ("preset_v2v_ref", "video", "参考视频", "v2v_ref"),
    ("preset_i2v_orbit", "video", "360全景", "i2v_orbit"),
    ("preset_avatar", "video", "数字人口播", "avatar"),
    ("preset_motion", "video", "动作迁移", "motion"),
    ("preset_video_analysis", "video", "视频分析", "video_analysis"),
)


def _menu_item(
    item_id: str,
    category: str,
    title: str,
    sub: str,
    *,
    bind_mode: str = "auto",
    targets: list[str] | None = None,
    default_id: str | None = None,
) -> dict[str, Any]:
    manual = [
        {"provider_id": None, "target_type": "workflow", "target_id": name} for name in (targets or [])
    ]
    default_target = None
    if default_id:
        default_target = {"provider_id": None, "target_type": "workflow", "target_id": default_id}
    return {
        "id": item_id,
        "category": category,
        "title": title,
        "hint": "",
        "sub_capability": sub,
        "bind_mode": bind_mode,
        "manual_targets": manual,
        "default_target": default_target,
        "enabled": True,
    }


def default_canvas_menu() -> list[dict[str, Any]]:
    """出厂菜单。图像和视频按当前工作流的最小功能手动指定，有越狱包时默认越狱包。"""
    from liberastra.services.workflows import list_packs

    grouped: dict[str, list[str]] = {row[3]: [] for row in _WORKFLOW_MENU_ROWS}
    for pack in list_packs():
        image_count = sum(
            1 for spec in pack.inputs.values() if isinstance(spec, dict) and spec.get("type") == "image"
        )
        sub = pack_sub_capability(pack.name, pack.capability, image_count)
        if sub in grouped:
            grouped[sub].append(pack.name)
    items = [
        _menu_item("preset_tts", "speech", "文字转语音", "tts"),
        _menu_item("preset_asr", "speech", "语音识别", "asr"),
    ]
    for item_id, category, title, sub in _WORKFLOW_MENU_ROWS:
        names = sorted(grouped[sub], key=lambda name: (0 if "uncensored" in name else 1, name))
        if not names:
            continue
        default_id = next((name for name in names if "uncensored" in name), names[0])
        items.append(
            _menu_item(
                item_id,
                category,
                title,
                sub,
                bind_mode="manual",
                targets=names,
                default_id=default_id,
            )
        )
    return items


def normalize_menu_item(raw: dict[str, Any]) -> dict[str, Any]:
    title = str(raw.get("title") or "").strip()
    if not 2 <= len(title) <= 10:
        raise ValueError(f"功能简称需为 2–10 个字：{title or '（空）'}")
    category = str(raw.get("category") or "")
    if category not in {"speech", "image", "video"}:
        raise ValueError("菜单分类只能是语音、图像或视频")
    sub = str(raw.get("sub_capability") or "")
    if sub not in SUB_CAPABILITIES:
        raise ValueError(f"未知细分能力: {sub}")
    bind_mode = str(raw.get("bind_mode") or "auto")
    if bind_mode not in {"auto", "manual"}:
        raise ValueError("绑定模式只能是 auto 或 manual")
    manual = []
    for target in raw.get("manual_targets") or []:
        if not isinstance(target, dict):
            continue
        target_type = str(target.get("target_type") or "")
        target_id = str(target.get("target_id") or "").strip()
        if target_type not in {"model", "workflow"} or not target_id:
            continue
        provider_id = target.get("provider_id")
        manual.append(
            {
                "provider_id": int(provider_id) if provider_id else None,
                "target_type": target_type,
                "target_id": target_id,
            }
        )
    default_target = raw.get("default_target")
    if isinstance(default_target, dict) and default_target.get("target_id"):
        default_target = {
            "provider_id": int(default_target["provider_id"])
            if default_target.get("provider_id")
            else None,
            "target_type": str(default_target.get("target_type") or "model"),
            "target_id": str(default_target["target_id"]),
        }
    else:
        default_target = None
    item_id = str(raw.get("id") or "").strip() or f"item_{sub}_{title}"
    return {
        "id": item_id[:64],
        "category": category,
        "title": title,
        "hint": str(raw.get("hint") or "")[:200],
        "sub_capability": sub,
        "bind_mode": bind_mode,
        "manual_targets": manual,
        "default_target": default_target,
        "enabled": bool(raw.get("enabled", True)),
    }
