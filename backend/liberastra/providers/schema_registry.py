"""把工作流包和云端模型收成同一种 ExecutionSpec。

GET /api/v1/providers/execution-specs 调用 workflow_specs 与 model_specs。
"""

from __future__ import annotations

from typing import Any

from liberastra.providers.base import ExecutionSpec, MediaSlotSpec
from liberastra.providers.catalog import execution_fields, media_slots, pack_sub_capability, read_catalog
from liberastra.providers.vendors.volcengine.schemas import apply_saved_defaults

_FORM_FIELDS = (
    "type",
    "label",
    "default",
    "description",
    "options",
    "options_from",
    "min",
    "max",
    "step",
    "required",
)


def _slots(raw: list[dict[str, Any]]) -> tuple[MediaSlotSpec, ...]:
    return tuple(
        MediaSlotSpec(
            key=item["key"],
            type=item["type"],
            label=item["label"],
            required=bool(item.get("required", True)),
            multiple=bool(item.get("multiple", False)),
            input_kind=str(item.get("input_kind") or item["type"]),
        )
        for item in raw
    )


def _form_inputs(pack_inputs: dict[str, Any]) -> dict[str, Any]:
    """去掉只给 Comfy 执行器用的 node/field，留下前端表单需要的字段。"""
    form: dict[str, Any] = {}
    for key, spec in pack_inputs.items():
        if not isinstance(spec, dict) or spec.get("type") in {"image", "video", "audio"}:
            continue
        form[key] = {field: spec[field] for field in _FORM_FIELDS if field in spec}
    return form


# 数字人口播、动作迁移在执行时会自己补提示词。画布只连真正要喂进去的媒体。
AUTO_PROMPT_CAPABILITIES = {"avatar", "motion"}


def slots_from_pack(capability: str, inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """工作流包的前置输入以实际执行为准。必填媒体都补；提示词只在用户必须手写时才补文本。"""
    slots: list[dict[str, Any]] = []
    for key, spec in inputs.items():
        if not isinstance(spec, dict):
            continue
        kind = spec.get("type")
        required = bool(spec.get("required", False))
        label = str(spec.get("label") or key)
        if kind in {"image", "video", "audio"}:
            input_kind = "character" if capability == "motion" and kind == "image" and required else kind
            slots.append(
                {
                    "key": key,
                    "type": kind,
                    "label": label,
                    "required": required,
                    "multiple": False,
                    "input_kind": input_kind,
                }
            )
        elif (
            key == "prompt"
            and kind == "str"
            and required
            and not str(spec.get("default") or "").strip()
            and capability not in AUTO_PROMPT_CAPABILITIES
        ):
            slots.append(
                {
                    "key": "prompt",
                    "type": "text",
                    "label": label or "提示词",
                    "required": True,
                    "multiple": False,
                    "input_kind": "text",
                }
            )
    return slots


def workflow_specs(packs: list[Any]) -> list[ExecutionSpec]:
    specs: list[ExecutionSpec] = []
    for pack in packs:
        image_count = sum(
            1
            for spec in pack.inputs.values()
            if isinstance(spec, dict) and spec.get("type") == "image"
        )
        sub = pack_sub_capability(pack.name, pack.capability, image_count)
        slots = slots_from_pack(pack.capability, pack.inputs)
        if pack.capability in {"t2i", "i2i", "upscale"}:
            category = "image"
        elif pack.capability == "analysis":
            category = "llm"
        elif pack.capability == "tts":
            category = "speech"
        else:
            category = "video"
        specs.append(
            ExecutionSpec(
                target_type="workflow",
                target_id=pack.name,
                display_name=pack.name,
                sub_capability=sub,
                provider_type="comfyui",
                category=category,
                media_slots=_slots(slots),
                inputs=_form_inputs(pack.inputs),
            )
        )
    return specs


def model_specs(provider: Any) -> list[ExecutionSpec]:
    """一个已启用模型的每个细分能力各一条契约。本地语音、Ollama 与云端走同一份目录。"""
    specs: list[ExecutionSpec] = []
    for item in read_catalog(provider.extra, provider.type):
        if not item.get("enabled"):
            continue
        for sub in item.get("sub_capabilities") or []:
            specs.append(
                ExecutionSpec(
                    target_type="model",
                    target_id=item["id"],
                    display_name=item.get("label") or item["id"],
                    sub_capability=sub,
                    provider_type=provider.type,
                    provider_id=provider.id,
                    provider_name=provider.name,
                    category=item.get("category") or "",
                    media_slots=_slots(media_slots(sub)),
                    inputs=apply_saved_defaults(
                        execution_fields(provider.type, sub),
                        (item.get("params") or {}).get("defaults"),
                    ),
                )
            )
    return specs


def filter_specs(
    specs: list[ExecutionSpec],
    *,
    sub_capability: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for spec in specs:
        if sub_capability and spec.sub_capability != sub_capability:
            continue
        if category and spec.category != category:
            continue
        rows.append(spec.to_dict())
    return rows
