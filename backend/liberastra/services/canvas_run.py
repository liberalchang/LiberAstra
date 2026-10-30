"""画布执行编排器：协程逐节点提交 Job 并等待，不占队列并发槽。

- scope：目标节点（缺省=所有末端节点）+ 其祖先链，拓扑序执行。
- 增量复用：指纹（包 + 解析后输入 + 上游资产 id）命中且上次成功则复用。
- 失败/取消的节点标记 failed，其下游在输入解析时报错跳过，其他分支继续。
- 运行状态：plan 存 app.state.canvas_runs（内存,实时）；节点结果持久化在 canvas_node_runs。
"""

from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from liberastra.core.db import SessionLocal
from liberastra.jobs.manager import JobManager
from liberastra.models import Asset, Canvas, CanvasNodeRun, Character, Job, Voice, utcnow
from liberastra.models.job import TERMINAL_STATUSES
from liberastra.providers.base import ProviderError
from liberastra.services.canvas_graph import (
    canonical_fingerprint,
    node_map,
    resolve_scope,
    substitute_prompt,
    topo_order,
)
from liberastra.services.characters import ensure_character_asset, expand_reference_paths, slot_path
from liberastra.services.workflows import WorkflowPack, get_pack
from liberastra.storage import resolve

MEDIA_KINDS = ("image", "video", "audio")


def start_run(
    app,  # noqa: ANN001 FastAPI
    canvas: Canvas,
    owner_id: int,
    node_ids: list[str],
    force_node_ids: list[str],
) -> tuple[str, list[dict[str, Any]]]:
    """启动一次画布执行,立即返回 run_id 与初始 plan(节点状态随后台推进)。"""
    graph = canvas.graph or {}
    scope = resolve_scope(graph, node_ids or None)
    order = topo_order(graph, scope)
    if not order:
        raise ProviderError("画布为空，没有可执行的节点")
    run_id = uuid.uuid4().hex
    plan = [
        {"node_id": nid, "job_id": None, "status": "pending", "reused": False} for nid in order
    ]
    runs = getattr(app.state, "canvas_runs", None)
    if runs is None:
        runs = app.state.canvas_runs = {}
    # 同画布的已结束执行只保留最新一次,避免内存累积
    for rid, state in list(runs.items()):
        if state["canvas_id"] == canvas.id and state["task"].done():
            del runs[rid]
    task = asyncio.create_task(
        _orchestrate(app, run_id, canvas.id, owner_id, order, set(force_node_ids))
    )
    runs[run_id] = {"canvas_id": canvas.id, "plan": plan, "task": task}
    return run_id, plan


def latest_plan(app, canvas_id: str) -> list[dict[str, Any]] | None:  # noqa: ANN001
    """内存中该画布最近一次执行的实时 plan；没有进行中的执行时返回 None。"""
    runs = getattr(app.state, "canvas_runs", {}) or {}
    for state in reversed(list(runs.values())):
        if state["canvas_id"] == canvas_id:
            return state["plan"]
    return None


# ---- 节点执行 ----


def _run_row(db: Session, canvas_id: str, node_id: str) -> CanvasNodeRun:
    row = db.scalar(
        select(CanvasNodeRun).where(
            CanvasNodeRun.canvas_id == canvas_id, CanvasNodeRun.node_id == node_id
        )
    )
    if row is None:
        row = CanvasNodeRun(canvas_id=canvas_id, node_id=node_id, status="idle", asset_ids=[])
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _text_variables(nodes: dict[str, dict[str, Any]]) -> dict[str, str]:
    """文本输入节点的 varName → 内容,供提示词 {{var}} 替换。"""
    out: dict[str, str] = {}
    for node in nodes.values():
        if node.get("type") != "input":
            continue
        data = node.get("data") or {}
        if str(data.get("mediaKind") or "") != "text":
            continue
        name = str(data.get("varName") or "").strip()
        if name:
            out[name] = str(data.get("text") or "")
    return out


def _incoming_sources(graph: dict[str, Any], node_id: str) -> list[str]:
    return [
        str(e.get("source"))
        for e in (graph.get("edges") or [])
        if str(e.get("target")) == node_id
    ]


def _upstream_assets(
    db: Session, graph: dict[str, Any], node_id: str, runs: dict[str, CanvasNodeRun]
) -> list[Asset]:
    """按连线顺序收集上游节点的产物资产；上游未成功则报错（自然跳过下游）。"""
    assets: list[Asset] = []
    for source in _incoming_sources(graph, node_id):
        run = runs.get(source)
        if run is None or run.status != "succeeded":
            raise ProviderError("上游节点尚未成功执行")
        for asset_id in run.asset_ids or []:
            asset = db.get(Asset, int(asset_id))
            if asset is not None:
                assets.append(asset)
    return assets


def _ordered_upstream(
    db: Session, graph: dict[str, Any], node_id: str, runs: dict[str, CanvasNodeRun]
) -> list[dict[str, Any]]:
    """按连线顺序收集上游。角色节点收成一条，避免四张视角图直接占满图片槽。"""
    nodes = node_map(graph)
    items: list[dict[str, Any]] = []
    for source in _incoming_sources(graph, node_id):
        run = runs.get(source)
        if run is None or run.status != "succeeded":
            raise ProviderError("上游节点尚未成功执行")
        data = (nodes.get(source) or {}).get("data") or {}
        if str(data.get("mediaKind") or "") == "character":
            by_slot: dict[str, Asset] = {}
            for asset_id in run.asset_ids or []:
                asset = db.get(Asset, int(asset_id))
                if asset is None:
                    continue
                slot = str((asset.meta or {}).get("character_slot") or "")
                if slot:
                    by_slot[slot] = asset
            items.append(
                {
                    "type": "character",
                    "primary": str(data.get("characterSlot") or "front"),
                    "paths": {slot: asset.path for slot, asset in by_slot.items()},
                    "assets": list(by_slot.values()),
                }
            )
            continue
        for asset_id in run.asset_ids or []:
            asset = db.get(Asset, int(asset_id))
            if asset is None:
                continue
            if (asset.meta or {}).get("canvas_mask"):
                items.append({"type": "mask", "asset": asset})
            else:
                items.append({"type": "file", "asset": asset})
    return items


def _materialize_input(db: Session, node: dict[str, Any], row: CanvasNodeRun, owner_id: int) -> None:
    data = node.get("data") or {}
    media_kind = str(data.get("mediaKind") or "text")
    if media_kind == "text":
        if not str(data.get("text") or "").strip():
            raise ProviderError("文本输入节点内容为空")
        row.asset_ids = []
    elif media_kind == "character":
        # 一个角色节点登记全部已有单人图，具体送哪几张由下游工作流槽位决定。
        character_id = data.get("characterId")
        character = db.get(Character, int(character_id)) if character_id else None
        if character is None or character.owner_id != owner_id:
            raise ProviderError("角色输入还没有选择角色")
        asset_ids: list[int] = []
        for slot in ("turnaround", "portrait", "front", "side", "back"):
            if not slot_path(character, slot):
                continue
            asset_ids.append(ensure_character_asset(db, character, slot).id)
        if not asset_ids:
            raise ProviderError("这个角色还没有可用的单人图")
        row.asset_ids = asset_ids
    else:
        asset_id = data.get("assetId")
        asset = db.get(Asset, int(asset_id)) if asset_id else None
        if asset is None:
            raise ProviderError("输入节点还没有选择文件")
        if asset.kind != media_kind:
            raise ProviderError(
                f"输入节点的文件类型（{asset.kind}）与节点类型（{media_kind}）不符"
            )
        row.asset_ids = [asset.id]
        # 蒙版(局部重绘用):跟在主图后面进资产链,打标 canvas_mask 供下游分流
        mask_id = data.get("maskAssetId")
        if mask_id:
            mask = db.get(Asset, int(mask_id))
            if mask is None or mask.kind != "image":
                raise ProviderError("蒙版资产不存在或不是图片")
            mask.hidden = True
            mask.meta = {**(mask.meta or {}), "canvas_mask": True, "canvas_node": node.get("id")}
            row.asset_ids.append(mask.id)
    row.status = "succeeded"
    row.error = None
    row.job_id = None
    row.updated_at = utcnow()
    db.commit()


_FAMILY_NOISE = re.compile(
    r"^(fp\d+|bf16|int\d+|nvfp4|awq|scaled|pruned|convrot|e4m3fn|master|model|v\d+|\d+|"
    r"image|video|audio|text|edit|upscale|checkpoint|lora|vae|unet|clip|safetensors)$"
)


def _image_keys_to_fill(pack: WorkflowPack, image_keys: list[str], upstream_count: int) -> list[str]:
    """决定这次要填哪些图片槽。

    带 fallback 的可选槽（360° 环绕的结束画面）不参与角色多视角展开。
    上游只有一张图或一个角色时留空，执行器会把首帧复制过去。
    用户另外接了第二张图时，才把这个槽算进去。
    """
    primary = [key for key in image_keys if not (pack.inputs.get(key) or {}).get("fallback")]
    fallback = [key for key in image_keys if (pack.inputs.get(key) or {}).get("fallback")]
    extra = max(upstream_count - len(primary), 0)
    count = len(primary) + min(len(fallback), extra)
    return (primary + fallback)[:count]


def _family_tokens(filename: str) -> set[str]:
    """从模型文件名提取家族词元(flux3、qwen_image 等),与前端 WorkflowInputs 的同款逻辑对应。"""
    base = re.split(r"[/\\]", filename)[-1].lower()
    base = re.sub(r"\.(safetensors|ckpt|pt|pth|bin|gguf)$", "", base)
    return {
        t for t in re.split(r"[^a-z0-9]+", base) if len(t) >= 2 and not _FAMILY_NOISE.match(t)
    }


def _canvas_soundtrack(pack: WorkflowPack, data: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    """数字人、动作迁移不采用用户填的时长。声音来源和背景音乐单独进指纹。"""
    if pack.capability not in ("avatar", "motion"):
        return {}
    inputs.pop("length", None)
    inputs.pop("frames", None)
    mode = str(data.get("audioMode") or "model")
    if pack.capability != "motion" or mode != "reference":
        mode = "model"
    raw_volume = data.get("bgmVolume")
    try:
        volume = float(0.2 if raw_volume in (None, "") else raw_volume)
    except (TypeError, ValueError):
        volume = 0.2
    return {
        "audio_mode": mode,
        "bgm_path": str(data.get("bgmPath") or "").strip(),
        "bgm_volume": volume,
    }


def _plain_text_from_job(db: Session, job_id: str | None) -> str:
    """任务输出里的纯文本。转写和画面分析都把正文放在 type=text。"""
    if not job_id:
        return ""
    job = db.get(Job, job_id)
    if job is None:
        return ""
    for block in job.outputs or []:
        if isinstance(block, dict) and block.get("type") == "text":
            content = str(block.get("content") or "").strip()
            if content:
                return content
    return ""


def _publish_node_text(variables: dict[str, str], node: dict[str, Any], text: str) -> None:
    """把节点产出的正文写进 {{变量名}}，供后续节点替换。"""
    name = str((node.get("data") or {}).get("varName") or "").strip()
    cleaned = text.strip()
    if name and cleaned:
        variables[name] = cleaned


def _output_text(db: Session, job_id: str | None, asset_ids: list[int] | None) -> str:
    """优先用任务里的纯文本；没有时再读文本或字幕资产。"""
    text = _plain_text_from_job(db, job_id)
    if text:
        return text
    parts: list[str] = []
    for asset_id in asset_ids or []:
        asset = db.get(Asset, int(asset_id))
        if asset is None or asset.kind not in ("text", "subtitle"):
            continue
        try:
            parts.append(resolve(asset.path).read_text(encoding="utf-8").strip())
        except OSError:
            continue
    return "\n".join(part for part in parts if part)


def _model_target(data: dict[str, Any]) -> Any:
    """云端模型节点用槽位声明冒充工作流包，后面的连线映射可以原样复用。"""
    from liberastra.providers.catalog import SUB_CAPABILITIES, media_slots
    from liberastra.services.model_media import VIDEO_SUBS

    sub = str(data.get("subCapability") or "t2i")
    if sub not in SUB_CAPABILITIES:
        raise ProviderError(f"未知细分能力: {sub}")
    target_id = str(data.get("targetId") or "").strip()
    if not target_id:
        raise ProviderError("功能节点还没有选择模型")
    inputs = {
        slot["key"]: {
            "type": slot["type"],
            "label": slot["label"],
            "required": slot["required"],
        }
        for slot in media_slots(sub)
    }
    inputs["prompt"] = {"type": "str", "required": False}

    class _Target:
        target_type = "model"
        name = target_id
        capability = "t2v" if sub in VIDEO_SUBS else "t2i"
        sub_capability = sub

    target = _Target()
    target.inputs = inputs
    return target


def _resolve_function_inputs(
    db: Session,
    graph: dict[str, Any],
    node: dict[str, Any],
    runs: dict[str, CanvasNodeRun],
    variables: dict[str, str],
) -> tuple[Any, dict[str, Any], str]:
    """解析功能节点的最终 inputs 与指纹。返回 (pack, inputs, fingerprint, soundtrack)。

    媒体输入优先级:槽位绑定(bindings: 参数名 → 上游变量名)> 按类型+连线顺序自动映射。
    """
    data = node.get("data") or {}
    if str(data.get("targetType") or "") == "model":
        pack = _model_target(data)
    else:
        pack_name = str(data.get("pack") or data.get("targetId") or "")
        if not pack_name:
            raise ProviderError("功能节点还没有选择工作流包")
        pack = get_pack(pack_name)
    inputs: dict[str, Any] = dict(data.get("values") or {})

    # PromptField 三件套:启用优化稿且有内容时,用优化稿做变量替换
    raw_prompt = str(data.get("prompt") or "")
    if data.get("promptUseOptimized"):
        optimized = str(data.get("promptOptimized") or "")
        if optimized.strip():
            raw_prompt = optimized
    prompt = substitute_prompt(raw_prompt, variables)
    # 画面分析的说明写在包参数 custom_prompt，不占用功能节点的提示词框
    if prompt.strip() and pack.capability != "analysis":
        inputs["prompt"] = prompt

    ordered = _ordered_upstream(db, graph, str(node["id"]), runs)
    media_paths: dict[str, list[str]] = {kind: [] for kind in MEDIA_KINDS}
    media_asset_ids: list[int] = []
    mask_paths: list[str] = []
    expand_items: list[dict[str, Any]] = []
    # 蒙版键:参数名是 mask,或 label/description 含「蒙版」——只有这些键吃蒙版资产,
    # 其余 image 键照常分流,避免蒙版挤占多图编辑的 image_2 槽位
    mask_keys = [
        k
        for k, s in pack.inputs.items()
        if s.get("type") == "image"
        and (
            k == "mask"
            or "蒙版" in str(s.get("label") or "")
            or "蒙版" in str(s.get("description") or "")
        )
    ]
    for item in ordered:
        if item["type"] == "mask":
            asset = item["asset"]
            mask_paths.append(asset.path)
            media_asset_ids.append(asset.id)
            continue
        if item["type"] == "character":
            for asset in item["assets"]:
                media_asset_ids.append(asset.id)
            expand_items.append(
                {"type": "character", "primary": item["primary"], "paths": item["paths"]}
            )
            continue
        asset = item["asset"]
        media_asset_ids.append(asset.id)
        if asset.kind == "image":
            expand_items.append({"type": "path", "path": asset.path})
        elif asset.kind in media_paths:
            media_paths[asset.kind].append(asset.path)
    image_keys = [
        k
        for k, s in pack.inputs.items()
        if s.get("type") == "image" and k not in mask_keys
    ]
    assign_keys = _image_keys_to_fill(pack, image_keys, len(expand_items))
    for key, path in zip(
        assign_keys,
        expand_reference_paths(str(pack.capability or ""), len(assign_keys), expand_items),
        strict=False,
    ):
        if not inputs.get(key):
            inputs[key] = path
    for media_kind, paths in media_paths.items():
        if media_kind == "image":
            continue
        keys = [k for k, s in pack.inputs.items() if s.get("type") == media_kind]
        for key, path in zip(keys, paths, strict=False):
            if not inputs.get(key):
                inputs[key] = path
    for key, path in zip(mask_keys, mask_paths, strict=False):
        if not inputs.get(key):
            inputs[key] = path

    # 槽位绑定:bindings 里指定的变量覆盖自动映射
    bindings = data.get("bindings") or {}
    if bindings:
        by_var: dict[str, list[Asset]] = {}
        nodes = node_map(graph)
        for nid, source_node in nodes.items():
            var = str((source_node.get("data") or {}).get("varName") or "")
            run = runs.get(nid)
            if not var or run is None or run.status != "succeeded":
                continue
            assets = [db.get(Asset, int(a)) for a in (run.asset_ids or [])]
            by_var[var] = [a for a in assets if a is not None]
            primary = str((source_node.get("data") or {}).get("characterSlot") or "")
            if primary:
                by_var[f"{var}::__primary"] = [
                    a for a in by_var[var] if (a.meta or {}).get("character_slot") == primary
                ]
        for key, spec in pack.inputs.items():
            if spec.get("type") not in MEDIA_KINDS:
                continue
            bound_var = str(bindings.get(key) or "").strip()
            if not bound_var:
                continue
            preferred = by_var.get(f"{bound_var}::__primary") or []
            candidates = preferred or [a for a in by_var.get(bound_var, []) if a.kind == spec["type"]]
            if not candidates:
                label = spec.get("label") or key
                raise ProviderError(
                    f"输入「{label}」绑定的变量 {bound_var} 没有可用的{spec['type']}产物"
                )
            inputs[key] = candidates[0].path

    for key, spec in pack.inputs.items():
        if spec.get("type") in MEDIA_KINDS and spec.get("required") and not inputs.get(key):
            label = spec.get("label") or key
            raise ProviderError(f"缺少必需的输入「{label}」，请连接对应类型的输入节点")

    accel = data.get("accel")
    if accel:
        inputs["__accel"] = accel

    # 旧画布节点可能残留上个包的模型文件名(前端换包已修,存量节点在此兜底):
    # options_from 参数值与包默认值的模型家族无共同词元时,回落包默认并告警
    for key, spec in pack.inputs.items():
        if not isinstance(spec, dict) or not spec.get("options_from"):
            continue
        value = str(inputs.get(key) or "").strip()
        default = str(spec.get("default") or "").strip()
        if not value or not default or value == default:
            continue
        if _family_tokens(value) & _family_tokens(default):
            continue
        logger.warning(
            f"画布节点参数 {key}={value} 与包 {pack.name} 的默认 {default} 家族不符,已回落默认"
        )
        inputs[key] = default

    soundtrack = _canvas_soundtrack(pack, data, inputs)
    fingerprint = canonical_fingerprint(
        {
            "pack": pack.name,
            "inputs": inputs,
            "media_asset_ids": sorted(media_asset_ids),
            **({"soundtrack": soundtrack} if soundtrack else {}),
        }
    )
    return pack, inputs, fingerprint, soundtrack


def _canvas_labels(db: Session, canvas_id: str, node: dict[str, Any]) -> dict[str, str]:
    """任务列表用的画布名和节点名。节点没有标题时退回包名或类型。"""
    canvas = db.get(Canvas, canvas_id)
    data = node.get("data") or {}
    label = ""
    for key in ("label", "title", "name", "pack", "workflow", "model"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            label = value.strip()
            break
    if not label:
        label = str(data.get("kind") or node.get("type") or "")
    return {
        "canvas_name": canvas.name if canvas is not None else "",
        "node_label": label,
    }


def _assets_alive(db: Session, asset_ids: list[int]) -> bool:
    return all(db.get(Asset, int(aid)) is not None for aid in asset_ids)


async def _wait_terminal(db: Session, manager: JobManager, job_id: str) -> Job:
    """订阅 SSE 队列等待终态；先订阅再查当前状态,避免错过已完成的事件。"""
    queue = manager.subscribe(job_id)
    try:
        job = db.get(Job, job_id)
        if job is not None and job.status in TERMINAL_STATUSES:
            return job
        while True:
            payload = await queue.get()
            if payload["job"]["status"] in TERMINAL_STATUSES:
                db.expire_all()
                finished = db.get(Job, job_id)
                assert finished is not None
                return finished
    finally:
        manager.unsubscribe(job_id, queue)


async def _execute_function(
    app,  # noqa: ANN001
    db: Session,
    canvas_id: str,
    owner_id: int,
    graph: dict[str, Any],
    node: dict[str, Any],
    row: CanvasNodeRun,
    runs: dict[str, CanvasNodeRun],
    variables: dict[str, str],
    force: set[str],
    item: dict[str, Any],
) -> None:
    node_id = str(node["id"])
    pack, inputs, fingerprint, soundtrack = _resolve_function_inputs(
        db, graph, node, runs, variables
    )
    reusable = (
        node_id not in force
        and row.status == "succeeded"
        and row.fingerprint == fingerprint
        and _assets_alive(db, list(row.asset_ids or []))
    )
    if reusable:
        if pack.capability == "analysis":
            _publish_node_text(variables, node, _output_text(db, row.job_id, list(row.asset_ids or [])))
        row.updated_at = utcnow()
        db.commit()
        item["status"] = "succeeded"
        item["reused"] = True
        return

    manager: JobManager = app.state.jobs
    provider_id = (node.get("data") or {}).get("providerId")
    if getattr(pack, "target_type", "") == "model":
        params = {
            "canvas_id": canvas_id,
            "node_id": node_id,
            "target_type": "model",
            "model": pack.name,
            "sub_capability": pack.sub_capability,
            "prompt": str(inputs.get("prompt") or ""),
            "inputs": inputs,
            **_canvas_labels(db, canvas_id, node),
        }
    else:
        params = {
            "canvas_id": canvas_id,
            "node_id": node_id,
            "workflow": pack.name,
            "inputs": inputs,
            **soundtrack,
            **_canvas_labels(db, canvas_id, node),
        }
    job = manager.submit(
        db,
        owner_id=owner_id,
        kind="canvas.node",
        params=params,
        provider_id=int(provider_id) if provider_id else None,
    )
    row.job_id = job.id
    row.status = "running"
    row.fingerprint = fingerprint
    row.error = None
    row.updated_at = utcnow()
    db.commit()
    item["job_id"] = job.id
    item["status"] = "running"

    final = await _wait_terminal(db, manager, job.id)
    if final.status == "succeeded":
        row.asset_ids = [
            int(o["asset_id"]) for o in final.outputs if o.get("type") == "asset" and o.get("asset_id")
        ]
        if pack.capability == "analysis":
            _publish_node_text(variables, node, _output_text(db, job.id, list(row.asset_ids or [])))
        row.status = "succeeded"
        row.error = None
    else:
        row.status = final.status
        row.error = final.error
    row.updated_at = utcnow()
    db.commit()
    item["status"] = row.status


async def _execute_concat(
    app,  # noqa: ANN001
    db: Session,
    canvas_id: str,
    owner_id: int,
    graph: dict[str, Any],
    node: dict[str, Any],
    row: CanvasNodeRun,
    runs: dict[str, CanvasNodeRun],
    force: set[str],
    item: dict[str, Any],
) -> None:
    node_id = str(node["id"])
    data = node.get("data") or {}
    media_kind = str(data.get("mediaKind") or "video")
    if media_kind not in ("audio", "video"):
        raise ProviderError(f"合成节点只支持音频/视频: {media_kind}")

    incoming = _incoming_sources(graph, node_id)
    ordered = [str(x) for x in (data.get("order") or [])]
    sources = [s for s in ordered if s in incoming] + [s for s in incoming if s not in ordered]
    if not sources:
        raise ProviderError("合成节点还没有连接输入")

    asset_ids: list[int] = []
    for source in sources:
        run = runs.get(source)
        if run is None or run.status != "succeeded":
            raise ProviderError("上游节点尚未成功执行")
        for asset_id in run.asset_ids or []:
            asset = db.get(Asset, int(asset_id))
            if asset is not None and asset.kind == media_kind:
                asset_ids.append(asset.id)
    if not asset_ids:
        raise ProviderError(f"合成节点没有可用的{media_kind}输入")

    fingerprint = canonical_fingerprint({"kind": media_kind, "asset_ids": asset_ids})
    reusable = (
        node_id not in force
        and row.status == "succeeded"
        and row.fingerprint == fingerprint
        and _assets_alive(db, list(row.asset_ids or []))
    )
    if reusable:
        row.updated_at = utcnow()
        db.commit()
        item["status"] = "succeeded"
        item["reused"] = True
        return

    manager: JobManager = app.state.jobs
    job = manager.submit(
        db,
        owner_id=owner_id,
        kind="media.concat",
        params={
            "canvas_id": canvas_id,
            "node_id": node_id,
            "asset_ids": asset_ids,
            "kind": media_kind,
            **_canvas_labels(db, canvas_id, node),
        },
    )
    row.job_id = job.id
    row.status = "running"
    row.fingerprint = fingerprint
    row.error = None
    row.updated_at = utcnow()
    db.commit()
    item["job_id"] = job.id
    item["status"] = "running"

    final = await _wait_terminal(db, manager, job.id)
    if final.status == "succeeded":
        row.asset_ids = [
            int(o["asset_id"]) for o in final.outputs if o.get("type") == "asset" and o.get("asset_id")
        ]
        row.status = "succeeded"
        row.error = None
    else:
        row.status = final.status
        row.error = final.error
    row.updated_at = utcnow()
    db.commit()
    item["status"] = row.status


async def _execute_speech(
    app,  # noqa: ANN001
    db: Session,
    canvas_id: str,
    owner_id: int,
    graph: dict[str, Any],
    node: dict[str, Any],
    row: CanvasNodeRun,
    runs: dict[str, CanvasNodeRun],
    variables: dict[str, str],
    force: set[str],
    item: dict[str, Any],
) -> None:
    """语音节点：tts=文字转语音（文本 + 音色）;asr=语音转文字（连入音频或视频）。"""
    node_id = str(node["id"])
    data = node.get("data") or {}
    mode = str(data.get("mode") or "tts")

    if mode == "tts":
        text = substitute_prompt(str(data.get("text") or ""), variables).strip()
        if not text:
            raise ProviderError("文字转语音节点还没有输入文本")
        voice_name = ""
        options: dict[str, Any] = {}
        voice_record_id = data.get("voiceRecordId")
        if voice_record_id:
            record = db.get(Voice, int(voice_record_id))
            if record is None or record.owner_id != owner_id:
                raise ProviderError("音色不存在")
            voice_name = record.voice_id or record.name
            if record.ref_audio_path:
                options["ref_audio"] = record.ref_audio_path
        # 非音色库服务(edge-tts/OpenAI/Comfy 包):音色名/模型/工作流直接取节点配置
        if not voice_name:
            voice_name = str(data.get("voice") or "")
        language = str(data.get("language") or "").strip()
        if language:
            options["language"] = language
        fmt = str(data.get("format") or "mp3").strip() or "mp3"
        if fmt not in {"mp3", "wav", "ogg_opus"}:
            fmt = "mp3"
        kind = "tts.synthesize"
        params: dict[str, Any] = {
            "text": text,
            "voice": voice_name,
            "format": fmt,
            "options": options,
        }
        workflow = str(data.get("workflow") or "")
        if workflow:
            params["workflow"] = workflow
        provider_id = data.get("providerId")
        model = str(data.get("model") or "") or None
        fingerprint = canonical_fingerprint(
            {"mode": mode, "provider": provider_id, "model": model, **params}
        )
    elif mode == "asr":
        media_assets = [
            a
            for a in _upstream_assets(db, graph, node_id, runs)
            if a.kind in ("audio", "video")
        ]
        if not media_assets:
            raise ProviderError("语音转文字节点需要连接一个音频或视频输入")
        kind = "asr.transcribe"
        provider_id = data.get("providerId")
        model = str(data.get("model") or "") or None
        asr_format = str(data.get("format") or "").strip()
        params = {
            "file_path": media_assets[0].path,
            "task": "transcribe",
            "language": str(data.get("language") or "") or None,
            "formats": [asr_format] if asr_format else None,
        }
        fingerprint = canonical_fingerprint(
            {"mode": mode, "provider": provider_id, "model": model, **params}
        )
    else:
        raise ProviderError(f"未知语音节点模式: {mode}")

    reusable = (
        node_id not in force
        and row.status == "succeeded"
        and row.fingerprint == fingerprint
        and _assets_alive(db, list(row.asset_ids or []))
    )
    if reusable:
        if mode == "asr":
            _publish_node_text(variables, node, _output_text(db, row.job_id, list(row.asset_ids or [])))
        row.updated_at = utcnow()
        db.commit()
        item["status"] = "succeeded"
        item["reused"] = True
        return

    manager: JobManager = app.state.jobs
    params.update(_canvas_labels(db, canvas_id, node))
    job = manager.submit(
        db,
        owner_id=owner_id,
        kind=kind,
        params=params,
        provider_id=int(provider_id) if provider_id else None,
        model=model,
    )
    row.job_id = job.id
    row.status = "running"
    row.fingerprint = fingerprint
    row.error = None
    row.updated_at = utcnow()
    db.commit()
    item["job_id"] = job.id
    item["status"] = "running"

    final = await _wait_terminal(db, manager, job.id)
    if final.status == "succeeded":
        # 语音 runner 复用全局实现,产物默认公开;画布产物统一转隐藏打标
        assets = db.scalars(select(Asset).where(Asset.job_id == job.id)).all()
        for asset in assets:
            asset.hidden = True
            asset.meta = {
                **(asset.meta or {}),
                "canvas_temp": True,
                "canvas_id": canvas_id,
                "canvas_node": node_id,
            }
        row.asset_ids = [a.id for a in assets]
        if mode == "asr":
            _publish_node_text(variables, node, _output_text(db, job.id, list(row.asset_ids or [])))
        row.status = "succeeded"
        row.error = None
    else:
        row.status = final.status
        row.error = final.error
    row.updated_at = utcnow()
    db.commit()
    item["status"] = row.status


async def _orchestrate(
    app,  # noqa: ANN001
    run_id: str,
    canvas_id: str,
    owner_id: int,
    order: list[str],
    force: set[str],
) -> None:
    state = app.state.canvas_runs[run_id]
    plan = {item["node_id"]: item for item in state["plan"]}
    db = SessionLocal()
    try:
        canvas = db.get(Canvas, canvas_id)
        if canvas is None:
            return
        graph = canvas.graph or {}
        nodes = node_map(graph)
        variables = _text_variables(nodes)
        runs: dict[str, CanvasNodeRun] = {}
        for node_id in order:
            node = nodes[node_id]
            item = plan[node_id]
            row = _run_row(db, canvas_id, node_id)
            try:
                node_type = node.get("type")
                if node_type == "input":
                    _materialize_input(db, node, row, owner_id)
                elif node_type == "function":
                    await _execute_function(
                        app, db, canvas_id, owner_id, graph, node, row, runs, variables,
                        force, item,
                    )
                elif node_type == "concat":
                    await _execute_concat(
                        app, db, canvas_id, owner_id, graph, node, row, runs, force, item
                    )
                elif node_type == "speech":
                    await _execute_speech(
                        app, db, canvas_id, owner_id, graph, node, row, runs, variables,
                        force, item,
                    )
                else:
                    raise ProviderError(f"未知节点类型: {node_type}")
            except Exception as exc:  # noqa: BLE001 —— 单节点失败不拖垮其他分支
                logger.warning("画布 {} 节点 {} 执行失败: {}", canvas_id, node_id, exc)
                db.rollback()
                row = _run_row(db, canvas_id, node_id)
                row.status = "failed"
                row.error = str(exc)[:500]
                row.updated_at = utcnow()
                db.commit()
                item["status"] = "failed"
            runs[node_id] = row
            item["status"] = row.status
            item["job_id"] = row.job_id
    finally:
        db.close()
