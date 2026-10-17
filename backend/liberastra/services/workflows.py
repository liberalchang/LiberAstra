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
    )
    validate_pack(pack)
    return pack


def list_packs(capability: str | None = None) -> list[WorkflowPack]:
    packs: dict[str, WorkflowPack] = {}
    for directory, source in ((_builtin_dir(), "builtin"), (_user_dir(), "user")):
        if not directory.exists():
            continue
        for pack_dir in sorted(directory.iterdir()):
            if not pack_dir.is_dir():
                continue
            pack = _load_pack(pack_dir, source)
            if pack is not None:
                packs[pack.name] = pack  # 用户包覆盖同名内置包
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
    return {
        "name": pack.name,
        "capability": pack.capability,
        "description": pack.description,
        "inputs": pack.inputs,
        "outputs": pack.outputs,
        "requirements": pack.requirements,
        "workflow": pack.workflow,
    }


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
