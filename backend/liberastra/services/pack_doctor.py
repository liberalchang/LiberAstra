"""工作流包体检：结构、节点、模型、默认值、对齐、输出、尺寸和 fps。"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from liberastra.models import Provider
from liberastra.providers.base import ProviderError
from liberastra.providers.comfyui.client import ComfyClient
from liberastra.services.providers import build_adapter
from liberastra.services.workflows import WorkflowPack, validate_pack

OUTPUT_KEYS = {"images", "videos", "gifs", "texts"}


def _item(name: str, status: str, *, optional: bool = False, hint: str = "") -> dict[str, Any]:
    return {"name": name, "status": status, "optional": optional, "hint": hint}


def _check(
    check_id: str,
    label: str,
    status: str = "pass",
    detail: str = "",
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "detail": detail,
        "items": items or [],
    }


def _worst(statuses: list[str]) -> str:
    """SKIP 不压过 PASS；只有全部无法验证时才返回 skip。"""
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    if statuses and all(status == "skip" for status in statuses):
        return "skip"
    return "pass"


def _overall_items(items: list[dict[str, Any]]) -> str:
    return _worst([item["status"] for item in items])


def _provider_payload(provider: Provider) -> dict[str, Any]:
    return {"id": provider.id, "name": provider.name, "base_url": provider.base_url}


@dataclass
class _Context:
    """一次体检内的远程查询缓存，避免重复拉 object_info 和模型目录。"""

    client: ComfyClient
    _object_info: dict[str, Any] | None = None
    _object_info_error: ProviderError | None = None
    _folders: dict[str, list[str] | ProviderError] = field(default_factory=dict)

    async def object_info(self) -> dict[str, Any]:
        if self._object_info is None and self._object_info_error is None:
            try:
                self._object_info = await self.client.object_info()
            except ProviderError as exc:
                self._object_info_error = exc
        if self._object_info_error is not None:
            raise self._object_info_error
        return self._object_info or {}

    async def folder(self, folder: str) -> list[str]:
        if folder not in self._folders:
            try:
                self._folders[folder] = await self.client.list_model_folder(folder)
            except ProviderError as exc:
                self._folders[folder] = exc
        value = self._folders[folder]
        if isinstance(value, ProviderError):
            raise value
        return value

    async def options(self, source: str) -> list[str]:
        if not source.startswith("node:"):
            return await self.folder(source)
        parts = source.split(":", 2)
        if len(parts) != 3:
            raise ProviderError(f"node 选项格式应为 node:<节点类型>:<字段名>，收到 {source}")
        _, node_type, field_name = parts
        info = await self.object_info()
        node = info.get(node_type)
        if not isinstance(node, dict):
            raise ProviderError(f"ComfyUI 中没有节点 {node_type}")
        for group in ("required", "optional"):
            spec = (node.get("input") or {}).get(group, {}).get(field_name)
            if isinstance(spec, list) and spec and isinstance(spec[0], list):
                return [str(value) for value in spec[0]]
        raise ProviderError(f"节点 {node_type} 的 {field_name} 不是下拉输入")


def _structure_check(pack: WorkflowPack) -> dict[str, Any]:
    try:
        validate_pack(pack)
    except (ProviderError, AttributeError, TypeError, ValueError) as exc:
        return _check("structure", "结构", "fail", str(exc))
    return _check("structure", "结构", "pass", f"参数 {len(pack.inputs)} 个，节点映射完整")


def _class_types(pack: WorkflowPack) -> list[str]:
    return sorted(
        {
            str(node.get("class_type"))
            for node in pack.workflow.values()
            if isinstance(node, dict) and node.get("class_type")
        }
    )


async def _nodes_check(ctx: _Context, pack: WorkflowPack) -> dict[str, Any]:
    classes = _class_types(pack)
    try:
        info = await ctx.object_info()
    except ProviderError as exc:
        return _check("nodes", "节点", "fail", f"无法读取 object_info: {exc}")
    missing = [name for name in classes if name not in info]
    if missing:
        return _check(
            "nodes",
            "节点",
            "fail",
            f"缺 {len(missing)} 个节点类型",
            [_item(name, "fail", hint="安装对应的 ComfyUI 自定义节点") for name in missing],
        )
    return _check("nodes", "节点", "pass", f"{len(classes)} 个 class_type 全部注册")


def _accel_lora(pack: WorkflowPack) -> dict[str, Any]:
    accel = pack.accel if isinstance(pack.accel, dict) else {}
    lora = accel.get("lora")
    return lora if isinstance(lora, dict) else {}


async def _models_check(ctx: _Context, pack: WorkflowPack) -> dict[str, Any]:
    requirements = pack.requirements if isinstance(pack.requirements, dict) else {}
    raw = requirements.get("models")
    if not isinstance(raw, list) or not raw:
        return _check("models", "模型", "skip", "未声明 requirements.models")

    accel_lora = str(_accel_lora(pack).get("recommended") or "").strip()
    optional_names = {Path(accel_lora).name} if accel_lora else set()
    items: list[dict[str, Any]] = []
    for entry in raw:
        name = str(entry or "").strip()
        if not name:
            continue
        folder, sep, relative = name.partition("/")
        if not sep or not relative:
            items.append(_item(name, "skip", hint="models 条目不是 folder/file，无法校验"))
            continue
        try:
            files = await ctx.folder(folder)
        except ProviderError as exc:
            items.append(_item(name, "skip", hint=f"无法读取目录 {folder}: {exc}"))
            continue
        if relative in files:
            items.append(_item(name, "pass"))
            continue
        basename_hit = next(
            (candidate for candidate in files if Path(candidate).name == Path(relative).name), None
        )
        optional = Path(relative).name in optional_names
        if basename_hit:
            items.append(
                _item(
                    name,
                    "warn",
                    optional=optional,
                    hint=f"文件在 {folder}/{basename_hit}，路径与声明不一致",
                )
            )
        elif optional:
            items.append(
                _item(
                    name,
                    "warn",
                    optional=True,
                    hint=f"Turbo 关闭时可忽略；放到 ComfyUI/models/{folder}/",
                )
            )
        else:
            items.append(
                _item(name, "fail", hint=f"放到 ComfyUI/models/{folder}/{relative}")
            )

    if accel_lora and not any(
        Path(str(entry)).name == Path(accel_lora).name for entry in raw
    ):
        try:
            files = await ctx.folder("loras")
        except ProviderError as exc:
            items.append(_item(f"loras/{accel_lora}", "skip", optional=True, hint=str(exc)))
        else:
            if Path(accel_lora).name in {Path(candidate).name for candidate in files}:
                items.append(_item(f"loras/{accel_lora}", "pass", optional=True))
            else:
                items.append(
                    _item(
                        f"loras/{accel_lora}",
                        "warn",
                        optional=True,
                        hint="Turbo 关闭时可忽略",
                    )
                )

    status = _overall_items(items)
    fails = sum(1 for item in items if item["status"] == "fail")
    warns = sum(1 for item in items if item["status"] == "warn")
    detail = f"{len(items)} 个模型，{fails} 个缺失"
    if warns:
        detail += f"，{warns} 个警告"
    return _check("models", "模型", status, detail, items)


async def _options_check(ctx: _Context, pack: WorkflowPack) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    inputs = pack.inputs if isinstance(pack.inputs, dict) else {}
    for key, spec in inputs.items():
        if not isinstance(spec, dict):
            continue
        source = str(spec.get("options_from") or "").strip()
        if source:
            try:
                candidates = await ctx.options(source)
            except ProviderError as exc:
                items.append(_item(f"{key} ({source})", "skip", hint=str(exc)))
                continue
            default = spec.get("default")
            if default in (None, ""):
                items.append(_item(f"{key} ({source})", "skip", hint="没有默认值"))
            elif str(default) not in candidates:
                items.append(
                    _item(
                        f"{key}={default}",
                        "warn",
                        hint=f"不在候选里（候选 {len(candidates)} 个）",
                    )
                )
            else:
                items.append(_item(f"{key}={default}", "pass"))
            continue
        options = spec.get("options")
        default = spec.get("default")
        if isinstance(options, list) and options and default not in (None, ""):
            if str(default) not in {str(option) for option in options}:
                items.append(_item(f"{key}={default}", "warn", hint="不在静态候选中"))
            else:
                items.append(_item(f"{key}={default}", "pass"))

    lora = _accel_lora(pack)
    source = str(lora.get("options_from") or "").strip()
    recommended = str(lora.get("recommended") or "").strip()
    if source and recommended:
        try:
            candidates = await ctx.options(source)
        except ProviderError as exc:
            items.append(_item(f"accel.lora ({source})", "skip", hint=str(exc)))
        else:
            if Path(recommended).name in {Path(candidate).name for candidate in candidates}:
                items.append(_item(f"accel.lora={recommended}", "pass", optional=True))
            else:
                items.append(
                    _item(
                        f"accel.lora={recommended}",
                        "warn",
                        optional=True,
                        hint="候选里没有推荐 LoRA",
                    )
                )

    if not items:
        return _check("options", "默认值", "skip", "没有 options_from/options 参数")
    return _check("options", "默认值", _overall_items(items), f"{len(items)} 个参数有候选", items)


def _alignment_check(pack: WorkflowPack) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    inputs = pack.inputs if isinstance(pack.inputs, dict) else {}
    for key, spec in inputs.items():
        if not isinstance(spec, dict):
            continue
        minimum = spec.get("min")
        maximum = spec.get("max")
        default = spec.get("default")
        base = int(spec.get("align_base") or 0)
        if base <= 0:
            if minimum is not None and maximum is not None and default is not None:
                if not (minimum <= default <= maximum):
                    items.append(
                        _item(
                            key,
                            "warn",
                            hint=f"默认值 {default} 不在 [{minimum}, {maximum}]",
                        )
                    )
                else:
                    items.append(_item(key, "pass"))
            continue
        offset = int(spec.get("align_offset") or 0)
        if offset < 0 or offset >= base:
            items.append(_item(key, "fail", hint=f"对齐规则无效：{base}n+{offset}"))
            continue
        low = int(minimum) if minimum is not None else 1
        high = int(maximum) if maximum is not None else None
        if high is not None and low > high:
            items.append(_item(key, "fail", hint=f"min {low} > max {high}"))
            continue
        k_min = math.ceil((low - offset) / base)
        if high is not None:
            k_max = math.floor((high - offset) / base)
            if k_max < k_min:
                items.append(
                    _item(
                        key,
                        "fail",
                        hint=f"在 [{low}, {high}] 内没有满足 {base}n+{offset} 的帧数",
                    )
                )
                continue
        if default is None:
            items.append(_item(key, "pass", hint=f"{base}n+{offset}"))
            continue
        value = int(default)
        if high is not None and not (low <= value <= high):
            items.append(_item(key, "warn", hint=f"默认值 {value} 不在 [{low}, {high}]"))
        elif (value - offset) % base != 0:
            items.append(_item(key, "warn", hint=f"默认值 {value} 未按 {base}n+{offset} 对齐"))
        else:
            items.append(_item(key, "pass", hint=f"{base}n+{offset}"))
    if not items:
        return _check("alignment", "对齐", "skip", "没有对齐参数")
    return _check("alignment", "对齐", _overall_items(items), f"{len(items)} 个参数有范围/对齐", items)


def _outputs_local_check(pack: WorkflowPack) -> dict[str, Any]:
    outputs = pack.outputs if isinstance(pack.outputs, dict) else {}
    node = str(outputs.get("node") or "")
    if not node:
        return _check("outputs", "输出", "fail", "没有声明 outputs.node")
    if node not in pack.workflow:
        return _check("outputs", "输出", "fail", f"outputs.node {node} 不在 workflow 中")
    key = str(outputs.get("key") or "")
    if key and key not in OUTPUT_KEYS:
        return _check("outputs", "输出", "fail", f"不支持的输出 key: {key}")
    texts = outputs.get("texts")
    if isinstance(texts, list):
        missing = []
        for item in texts:
            node_id = str(item.get("node") if isinstance(item, dict) else item)
            if node_id and node_id not in pack.workflow:
                missing.append(node_id)
        if missing:
            return _check("outputs", "输出", "fail", f"texts 节点不存在: {', '.join(missing)}")
    return _check("outputs", "输出", "pass", f"输出节点 {node} 存在")


async def _outputs_check(ctx: _Context, pack: WorkflowPack) -> dict[str, Any]:
    local = _outputs_local_check(pack)
    if local["status"] == "fail":
        return local
    node = str((pack.outputs if isinstance(pack.outputs, dict) else {}).get("node") or "")
    try:
        info = await ctx.object_info()
    except ProviderError as exc:
        return _check("outputs", "输出", "skip", f"节点存在，但无法读取 object_info: {exc}")
    workflow_node = pack.workflow.get(node)
    class_type = str(workflow_node.get("class_type") or "") if isinstance(workflow_node, dict) else ""
    node_info = info.get(class_type)
    if not isinstance(node_info, dict) or not node_info.get("output"):
        return _check(
            "outputs",
            "输出",
            "fail",
            f"节点 {node}（{class_type or '未知类型'}）在 object_info 中没有输出",
        )
    return _check("outputs", "输出", "pass", f"输出节点 {node} 可用")


def _size_check(pack: WorkflowPack) -> dict[str, Any]:
    if not isinstance(pack.size, dict) or not pack.size:
        return _check("size", "尺寸", "skip", "没有 size 声明")
    items: list[dict[str, Any]] = []
    inputs = pack.inputs if isinstance(pack.inputs, dict) else {}
    for key in ("width", "height"):
        spec = inputs.get(key)
        if not isinstance(spec, dict):
            continue
        multiple = spec.get("multiple")
        default = spec.get("default")
        minimum = spec.get("min")
        maximum = spec.get("max")
        if multiple and default is not None:
            try:
                if int(default) % int(multiple) != 0:
                    items.append(
                        _item(key, "warn", hint=f"默认值 {default} 不是 {multiple} 的倍数")
                    )
            except (TypeError, ValueError):
                items.append(_item(key, "warn", hint="默认值不是整数"))
        if default is not None and minimum is not None and maximum is not None:
            try:
                if not (minimum <= default <= maximum):
                    items.append(
                        _item(key, "warn", hint=f"默认值 {default} 不在 [{minimum}, {maximum}]")
                    )
            except TypeError:
                items.append(_item(key, "warn", hint="min/max/default 类型不一致"))
    if not items:
        return _check("size", "尺寸", "pass", "size 声明完整")
    return _check("size", "尺寸", _overall_items(items), f"{len(items)} 个尺寸参数", items)


def _fps_check(pack: WorkflowPack) -> dict[str, Any]:
    if not pack.fps:
        return _check("fps", "帧率", "skip", "没有声明 fps")
    nodes = [
        node
        for node in pack.workflow.values()
        if isinstance(node, dict) and node.get("class_type") == "CreateVideo"
    ]
    if not nodes:
        return _check("fps", "帧率", "skip", "workflow 没有 CreateVideo 节点")
    linked = False
    mismatches: list[Any] = []
    for node in nodes:
        value = (node.get("inputs") or {}).get("fps")
        if isinstance(value, list):
            linked = True
        elif isinstance(value, (int, float)) and float(value) != float(pack.fps):
            mismatches.append(value)
    if mismatches:
        return _check(
            "fps",
            "帧率",
            "warn",
            f"CreateVideo.fps 与 manifest fps {pack.fps} 不一致",
            [_item(str(value), "warn") for value in mismatches],
        )
    if linked:
        return _check("fps", "帧率", "skip", "CreateVideo.fps 是连线，无法静态比对")
    return _check("fps", "帧率", "pass", f"fps={pack.fps}")


async def diagnose_pack(
    pack: WorkflowPack,
    provider: Provider,
    *,
    client: ComfyClient | None = None,
) -> dict[str, Any]:
    """对指定包和 ComfyUI Provider 跑完整检查。"""
    if client is None:
        adapter = build_adapter(provider)
        client = getattr(adapter, "client", None)
    if client is None:
        raise ProviderError(f"Provider {provider.name} 不是 ComfyUI")

    ctx = _Context(client)
    checks = [
        _structure_check(pack),
        await _nodes_check(ctx, pack),
        await _models_check(ctx, pack),
        await _options_check(ctx, pack),
        _alignment_check(pack),
        await _outputs_check(ctx, pack),
        _size_check(pack),
        _fps_check(pack),
    ]
    summary = {
        status: sum(1 for check in checks if check["status"] == status)
        for status in ("pass", "warn", "fail", "skip")
    }
    return {
        "pack": pack.name,
        "provider": _provider_payload(provider),
        "status": _worst([check["status"] for check in checks]),
        "checked_at": datetime.now(UTC).isoformat(),
        "summary": summary,
        "checks": checks,
    }


def offline_pack_warnings(pack: WorkflowPack) -> list[str]:
    """导入/保存后可离线做的检查，返回给界面展示的提示。"""
    checks = [
        _structure_check(pack),
        _alignment_check(pack),
        _size_check(pack),
        _fps_check(pack),
        _outputs_local_check(pack),
    ]
    warnings: list[str] = []
    for check in checks:
        items = check.get("items") or []
        for item in items:
            if item["status"] in {"warn", "fail"}:
                hint = f": {item['hint']}" if item.get("hint") else ""
                warnings.append(f"{check['label']} · {item['name']}{hint}")
        if not items and check["status"] in {"warn", "fail"}:
            warnings.append(f"{check['label']}: {check.get('detail') or check['status']}")
    return warnings


def doctor_error_result(pack_name: str, provider: Provider, detail: str) -> dict[str, Any]:
    """包无法解析时也能返回结构化结果，而不是 500。"""
    return {
        "pack": pack_name,
        "provider": _provider_payload(provider),
        "status": "fail",
        "checked_at": datetime.now(UTC).isoformat(),
        "summary": {"pass": 0, "warn": 0, "fail": 1, "skip": 0},
        "checks": [_check("structure", "结构", "fail", detail)],
    }
