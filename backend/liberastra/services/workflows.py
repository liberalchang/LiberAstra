"""工作流包（Workflow Pack）：workflow.json（API Format）+ manifest.yaml。

- 内置包在 backend/workflows/，用户包在 data/workflows/，合并加载，用户包可覆盖同名内置包。
- manifest 声明 capability、inputs（参数 → node_id.inputs.field 映射、类型、默认值、范围）、outputs。
- 注入方式：深拷贝 workflow 后按 manifest 显式映射注入参数（Dreamifly 风格）。
"""

from __future__ import annotations

import json
import random
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from liberastra.core.config import get_settings
from liberastra.providers.base import ProviderError

# 提交 inputs 里的保留键：加速开关参数，不映射到工作流节点
ACCEL_INPUT_KEY = "__accel"


@dataclass
class WorkflowPack:
    name: str
    capability: str
    description: str
    inputs: dict[str, dict[str, Any]]  # 参数名 → {node, field, type, default, min, max, required}
    outputs: dict[str, Any]  # {node, key}
    workflow: dict[str, Any]
    source: str  # builtin / user
    requirements: dict[str, Any] = field(default_factory=dict)
    fps: int | None = None  # 视频包的帧率（manifest 顶层 fps）；有它前端可按秒设置时长
    accel: dict[str, Any] = field(default_factory=dict)  # manifest 顶层 accel：加速 LoRA 声明，空=无加速能力
    # manifest 顶层 llm_note：给提示词优化器的技术上下文(事实密度优先);
    # 缺省时 _workflow_context 回落 description
    llm_note: str = ""


def _builtin_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "workflows"


def _user_dir() -> Path:
    return get_settings().data_dir / "workflows"


def _load_pack(pack_dir: Path, source: str) -> WorkflowPack | None:
    workflow_file = pack_dir / "workflow.json"
    manifest_file = pack_dir / "manifest.yaml"
    if not workflow_file.exists() or not manifest_file.exists():
        return None
    try:
        workflow = json.loads(workflow_file.read_text(encoding="utf-8"))
        manifest = yaml.safe_load(manifest_file.read_text(encoding="utf-8")) or {}
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ProviderError(f"工作流包 {pack_dir.name} 解析失败: {exc}") from exc

    pack = WorkflowPack(
        name=manifest.get("name", pack_dir.name),
        capability=manifest.get("capability", "t2i"),
        description=manifest.get("description", ""),
        inputs=manifest.get("inputs", {}),
        outputs=manifest.get("outputs", {}),
        workflow=workflow,
        source=source,
        requirements=manifest.get("requirements", {}),
        fps=manifest.get("fps"),
        accel=manifest.get("accel") or {},
        llm_note=str(manifest.get("llm_note") or ""),
    )
    validate_pack(pack)
    return pack


def list_packs(capability: str | None = None) -> list[WorkflowPack]:
    packs: dict[str, WorkflowPack] = {}
    builtin_notes: dict[str, str] = {}
    for directory, source in ((_builtin_dir(), "builtin"), (_user_dir(), "user")):
        if not directory.exists():
            continue
        for pack_dir in sorted(directory.iterdir()):
            if not pack_dir.is_dir():
                continue
            pack = _load_pack(pack_dir, source)
            if pack is None:
                continue
            if source == "builtin":
                if pack.llm_note:
                    builtin_notes[pack.name] = pack.llm_note
            else:
                # 用户包覆盖同名内置包,但没写 llm_note 时继承内置的
                # (同名即同源:用户包多由内置包导入改造而来;回落链:用户 llm_note → 内置 llm_note → description)
                if not pack.llm_note and pack.name in builtin_notes:
                    pack.llm_note = builtin_notes[pack.name]
            packs[pack.name] = pack
    result = list(packs.values())
    if capability:
        result = [p for p in result if p.capability == capability]
    return result


def get_pack(name: str) -> WorkflowPack:
    for pack in list_packs():
        if pack.name == name:
            return pack
    raise ProviderError(f"工作流包不存在: {name}")


def validate_pack(pack: WorkflowPack) -> None:
    for key, spec in pack.inputs.items():
        node = str(spec.get("node", ""))
        if node not in pack.workflow:
            raise ProviderError(f"工作流包 {pack.name} 参数 {key} 指向不存在的节点 {node}")
        if not spec.get("field"):
            raise ProviderError(f"工作流包 {pack.name} 参数 {key} 缺少 field 映射")
    if pack.accel:
        _validate_accel(pack)


def _validate_accel(pack: WorkflowPack) -> None:
    """校验 accel 声明：节点存在，bypass_input 是连线，源节点存在；下游只允许引用输出 0。"""
    spec = pack.accel
    node_id = str(spec.get("node", ""))
    if not node_id:
        raise ProviderError(f"工作流包 {pack.name} 的 accel 缺少 node")
    if node_id not in pack.workflow:
        raise ProviderError(f"工作流包 {pack.name} 的 accel.node {node_id} 在图里不存在")
    bypass = spec.get("bypass_input", "model")
    source = pack.workflow[node_id].get("inputs", {}).get(bypass)
    if not (isinstance(source, list) and len(source) == 2):
        raise ProviderError(
            f"工作流包 {pack.name} 的 accel.bypass_input「{bypass}」必须是连线类型"
        )
    src_node = str(source[0])
    if src_node not in pack.workflow:
        raise ProviderError(
            f"工作流包 {pack.name} 的 accel bypass 源节点 {src_node} 在图里不存在"
        )
    for other_id, other in pack.workflow.items():
        if other_id == node_id or not isinstance(other, dict):
            continue
        for value in other.get("inputs", {}).values():
            if isinstance(value, list) and len(value) == 2 and str(value[0]) == node_id:
                if int(value[1]) != 0:
                    raise ProviderError(
                        f"工作流包 {pack.name} 的 accel 节点只支持单路 MODEL 输出（slot 0），"
                        f"节点 {other_id} 引用了 slot {value[1]}"
                    )
    for preset_key in (spec.get("preset") or {}):
        if preset_key not in pack.inputs:
            raise ProviderError(
                f"工作流包 {pack.name} 的 accel.preset 引用了未声明的输入 {preset_key}"
            )


def import_pack(
    name: str,
    workflow: dict[str, Any],
    manifest: dict[str, Any],
    *,
    overwrite: bool = False,
) -> WorkflowPack:
    safe_name = "".join(c for c in name if c.isalnum() or c in "-_") or "pack"
    pack_dir = _user_dir() / safe_name
    if pack_dir.exists() and not overwrite:
        raise ProviderError(f"工作流包已存在: {safe_name}（可设 overwrite）")
    manifest = {**manifest, "name": manifest.get("name", safe_name)}
    pack = WorkflowPack(
        name=manifest["name"],
        capability=manifest.get("capability", "t2i"),
        description=manifest.get("description", ""),
        inputs=manifest.get("inputs", {}),
        outputs=manifest.get("outputs", {}),
        workflow=workflow,
        source="user",
        requirements=manifest.get("requirements", {}),
        fps=manifest.get("fps"),
        accel=manifest.get("accel") or {},
        llm_note=str(manifest.get("llm_note") or ""),
    )
    validate_pack(pack)
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "workflow.json").write_text(
        json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (pack_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return pack


def update_pack(name: str, workflow: dict[str, Any], manifest: dict[str, Any]) -> WorkflowPack:
    """编辑已存在的用户包（内置包不可编辑）。"""
    pack_dir = _user_dir() / name
    if not pack_dir.exists():
        raise ProviderError(f"用户工作流包不存在: {name}（内置包不可编辑）")
    return import_pack(name, workflow, manifest, overwrite=True)


def export_pack(name: str) -> dict[str, Any]:
    """导出完整包（manifest + workflow），可用于备份或在其他实例导入。"""
    pack = get_pack(name)
    data: dict[str, Any] = {
        "name": pack.name,
        "capability": pack.capability,
        "description": pack.description,
        "inputs": pack.inputs,
        "outputs": pack.outputs,
        "requirements": pack.requirements,
        "workflow": pack.workflow,
    }
    if pack.fps is not None:
        data["fps"] = pack.fps
    if pack.accel:
        data["accel"] = pack.accel
    if pack.llm_note:
        data["llm_note"] = pack.llm_note
    return data


def delete_pack(name: str) -> None:
    pack_dir = _user_dir() / name
    if not pack_dir.exists():
        raise ProviderError(f"用户工作流包不存在: {name}（内置包不可删除）")
    import shutil

    shutil.rmtree(pack_dir)


def _set_field(workflow: dict, node: str, field_path: str, value: Any) -> None:
    target: Any = workflow[str(node)]
    parts = field_path.split(".")
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value


def apply_inputs(pack: WorkflowPack, values: dict[str, Any]) -> dict[str, Any]:
    """深拷贝 workflow 并按 manifest 注入参数。seed=-1 替换为随机值。"""
    workflow = deepcopy(pack.workflow)
    for key, spec in pack.inputs.items():
        value = values.get(key, spec.get("default"))
        if value is None:
            if spec.get("required"):
                raise ProviderError(f"缺少必填参数: {key}")
            continue
        ptype = spec.get("type")
        if ptype == "image":
            continue  # 图像输入由调用方上传 ComfyUI 后回填（见 inject_image_input）
        if ptype == "int":
            value = int(value)
            if key == "seed" and value == -1:
                value = random.randint(0, 2**31 - 1)
            if "min" in spec:
                value = max(int(spec["min"]), value)
            if "max" in spec:
                value = min(int(spec["max"]), value)
        elif ptype == "float":
            value = float(value)
        elif ptype == "bool":
            value = bool(value)
        else:
            value = str(value)
        _set_field(workflow, str(spec["node"]), spec["field"], value)
    return workflow


def inject_image_input(workflow: dict, pack: WorkflowPack, key: str, comfy_name: str) -> None:
    """图像输入上传 ComfyUI 后，把返回的文件名注入对应节点。"""
    spec = pack.inputs[key]
    _set_field(workflow, str(spec["node"]), spec["field"], comfy_name)


def extract_accel(inputs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """从提交 inputs 拆出保留键 __accel，返回 (节点参数, accel 或 None)。"""
    clean = {k: v for k, v in inputs.items() if k != ACCEL_INPUT_KEY}
    raw = inputs.get(ACCEL_INPUT_KEY)
    if raw is None:
        return clean, None
    if not isinstance(raw, dict):
        raise ProviderError(f"{ACCEL_INPUT_KEY} 必须是 JSON 对象")
    return clean, raw


def _as_bool(value: Any, *, field: str) -> bool:
    """只接受 JSON 布尔，避免 bool(\"false\") == True。"""
    if isinstance(value, bool):
        return value
    raise ProviderError(f"{field} 必须是布尔值 true/false")


def resolve_accel_enabled(pack: WorkflowPack, accel: dict[str, Any] | None) -> bool:
    """包未声明 accel 时视为关闭；声明了则看 accel.enabled，缺省用 default_enabled。"""
    if not pack.accel:
        return False
    if accel is None:
        return _as_bool(pack.accel.get("default_enabled", False), field="accel.default_enabled")
    if "enabled" in accel:
        return _as_bool(accel["enabled"], field="__accel.enabled")
    return _as_bool(pack.accel.get("default_enabled", False), field="accel.default_enabled")


def resolve_accel_lora(pack: WorkflowPack, accel: dict[str, Any] | None) -> str:
    """开启加速时要用的 LoRA 文件名（显式选择 > recommended）。"""
    spec = pack.accel
    cfg = accel or {}
    return str(cfg.get("lora") or spec.get("lora", {}).get("recommended") or "")


def apply_accel(
    workflow: dict[str, Any],
    pack: WorkflowPack,
    accel: dict[str, Any] | None,
    *,
    user_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """按包的 accel 声明改写计算图（在 apply_inputs 之后调用）。

    开启：注入 LoRA 文件名与强度，并对用户未显式传入的输入应用 preset。
    关闭：把 accel 节点从图里摘掉，所有引用该节点的下游输入改接到
    bypass_input 的原始来源。无 accel 声明时原样返回。
    """
    spec = pack.accel
    if not spec:
        return workflow
    node_id = str(spec.get("node", ""))
    node = workflow.get(node_id)
    if node is None:
        raise ProviderError(f"工作流包 {pack.name} 的 accel.node {node_id} 在图里不存在")

    if resolve_accel_enabled(pack, accel):
        lora = resolve_accel_lora(pack, accel)
        if not lora:
            raise ProviderError("开启了加速但没有选择加速模型")
        lora_spec = spec.get("lora", {})
        _set_field(workflow, node_id, lora_spec.get("field", "inputs.lora_name"), lora)
        strength_spec = spec.get("strength", {})
        if strength_spec.get("field"):
            cfg = accel or {}
            raw_strength = cfg.get("strength", strength_spec.get("default", 1.0))
            try:
                strength = float(raw_strength)
            except (TypeError, ValueError) as exc:
                raise ProviderError(f"加速强度无效: {raw_strength}") from exc
            if "min" in strength_spec:
                strength = max(float(strength_spec["min"]), strength)
            if "max" in strength_spec:
                strength = min(float(strength_spec["max"]), strength)
            _set_field(workflow, node_id, strength_spec["field"], strength)
        # preset：用户手动改过的值优先（已在 apply_inputs 写入）
        provided = user_values or {}
        for key, preset_val in (spec.get("preset") or {}).items():
            if key in provided:
                continue
            input_spec = pack.inputs.get(key)
            if not input_spec:
                continue
            value: Any = preset_val
            ptype = input_spec.get("type")
            if ptype == "int":
                value = int(value)
            elif ptype == "float":
                value = float(value)
            elif ptype == "bool":
                value = bool(value)
            else:
                value = str(value)
            _set_field(workflow, str(input_spec["node"]), input_spec["field"], value)
        return workflow

    # 关闭：摘除节点；仅把引用输出 slot 0 的下游改接到 bypass_input 来源
    bypass = spec.get("bypass_input", "model")
    source = node.get("inputs", {}).get(bypass)
    if not (isinstance(source, list) and len(source) == 2):
        raise ProviderError(
            f"工作流包 {pack.name} 关闭加速失败：bypass_input「{bypass}」不是连线"
        )
    rewired = [source[0], source[1]]
    for other in workflow.values():
        if not isinstance(other, dict):
            continue
        for input_key, value in list(other.get("inputs", {}).items()):
            if isinstance(value, list) and len(value) == 2 and str(value[0]) == node_id:
                if int(value[1]) != 0:
                    raise ProviderError(
                        f"关闭加速失败：存在对 accel 节点非 0 输出的引用（slot {value[1]}）"
                    )
                other["inputs"][input_key] = list(rewired)
    del workflow[node_id]
    return workflow
