"""画布执行编排器：协程逐节点提交 Job 并等待，不占队列并发槽。

- scope：目标节点（缺省=所有末端节点）+ 其祖先链，拓扑序执行。
- 增量复用：指纹（包 + 解析后输入 + 上游资产 id）命中且上次成功则复用。
- 失败/取消的节点标记 failed，其下游在输入解析时报错跳过，其他分支继续。
- 运行状态：plan 存 app.state.canvas_runs（内存,实时）；节点结果持久化在 canvas_node_runs。
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from liberastra.core.db import SessionLocal
from liberastra.jobs.manager import JobManager
from liberastra.models import Asset, Canvas, CanvasNodeRun, Job, Voice, utcnow
from liberastra.models.job import TERMINAL_STATUSES
from liberastra.providers.base import ProviderError
from liberastra.services.canvas_graph import (
    canonical_fingerprint,
    node_map,
    resolve_scope,
    substitute_prompt,
    topo_order,
)
from liberastra.services.workflows import get_pack

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


def _materialize_input(db: Session, node: dict[str, Any], row: CanvasNodeRun) -> None:
    data = node.get("data") or {}
    media_kind = str(data.get("mediaKind") or "text")
    if media_kind == "text":
        if not str(data.get("text") or "").strip():
            raise ProviderError("文本输入节点内容为空")
        row.asset_ids = []
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
    row.status = "succeeded"
    row.error = None
    row.job_id = None
    row.updated_at = utcnow()
    db.commit()


def _resolve_function_inputs(
    db: Session,
    graph: dict[str, Any],
    node: dict[str, Any],
    runs: dict[str, CanvasNodeRun],
    variables: dict[str, str],
) -> tuple[Any, dict[str, Any], str]:
    """解析功能节点的最终 inputs 与指纹。返回 (pack, inputs, fingerprint)。

    媒体输入优先级:槽位绑定(bindings: 参数名 → 上游变量名)> 按类型+连线顺序自动映射。
    """
    data = node.get("data") or {}
    pack_name = str(data.get("pack") or "")
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
    if prompt.strip():
        inputs["prompt"] = prompt

    upstream = _upstream_assets(db, graph, str(node["id"]), runs)
    media_paths: dict[str, list[str]] = {kind: [] for kind in MEDIA_KINDS}
    media_asset_ids: list[int] = []
    for asset in upstream:
        if asset.kind in media_paths:
            media_paths[asset.kind].append(asset.path)
            media_asset_ids.append(asset.id)
    for media_kind, paths in media_paths.items():
        keys = [k for k, s in pack.inputs.items() if s.get("type") == media_kind]
        for key, path in zip(keys, paths, strict=False):
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
        for key, spec in pack.inputs.items():
            if spec.get("type") not in MEDIA_KINDS:
                continue
            bound_var = str(bindings.get(key) or "").strip()
            if not bound_var:
                continue
            candidates = [a for a in by_var.get(bound_var, []) if a.kind == spec["type"]]
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

    fingerprint = canonical_fingerprint(
        {"pack": pack.name, "inputs": inputs, "media_asset_ids": sorted(media_asset_ids)}
    )
    return pack, inputs, fingerprint


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
    pack, inputs, fingerprint = _resolve_function_inputs(db, graph, node, runs, variables)
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
        kind="canvas.node",
        params={
            "canvas_id": canvas_id,
            "node_id": node_id,
            "workflow": pack.name,
            "inputs": inputs,
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
    """语音节点：tts=文字转语音（文本 + 音色）;asr=语音转文字（连入音频输入）。"""
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
        kind = "tts.synthesize"
        params: dict[str, Any] = {
            "text": text,
            "voice": voice_name,
            "format": "mp3",
            "options": options,
        }
        fingerprint = canonical_fingerprint({"mode": mode, **params})
    elif mode == "asr":
        audio_assets = [
            a for a in _upstream_assets(db, graph, node_id, runs) if a.kind == "audio"
        ]
        if not audio_assets:
            raise ProviderError("语音转文字节点需要连接一个音频输入")
        kind = "asr.transcribe"
        params = {
            "file_path": audio_assets[0].path,
            "task": "transcribe",
            "language": str(data.get("language") or "") or None,
        }
        fingerprint = canonical_fingerprint({"mode": mode, **params})
    else:
        raise ProviderError(f"未知语音节点模式: {mode}")

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
    job = manager.submit(db, owner_id=owner_id, kind=kind, params=params)
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
                    _materialize_input(db, node, row)
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
