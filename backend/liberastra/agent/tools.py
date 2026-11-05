"""导演台工具清单与执行。服务端工具在这里跑，画布工具交给浏览器。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from liberastra.agent.script_runner import run_skill_script
from liberastra.agent.skills import (
    list_skill_files,
    read_skill,
    read_skill_file,
    save_skill_file,
    save_skill_text,
)
from liberastra.core.config import get_settings
from liberastra.media import ffmpeg
from liberastra.models import (
    AgentSession,
    Asset,
    Character,
    Job,
    Provider,
    User,
    Voice,
)
from liberastra.providers.base import ProviderError
from liberastra.services.canvas_menu import resolve_menu_items
from liberastra.services.providers import pick_llm_with_model, pick_provider
from liberastra.services.workflows import list_packs
from liberastra.storage import resolve

CLIENT_TOOL_NAMES = {
    "canvas_get_graph",
    "canvas_get_node",
    "canvas_get_node_schema",
    "canvas_add_node",
    "canvas_apply_menu",
    "canvas_apply_pack",
    "canvas_update_node",
    "canvas_connect",
    "canvas_disconnect",
    "canvas_set_binding",
    "canvas_layout",
    "canvas_delete_nodes",
    "canvas_run_nodes",
}
def _fn(
    name: str,
    description: str,
    properties: dict[str, Any] | None = None,
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


_STR = {"type": "string"}
_INT = {"type": "integer"}
_BOOL = {"type": "boolean"}
_OBJ = {"type": "object"}
_ARR = {"type": "array", "items": {"type": "string"}}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    _fn(
        "ask_user",
        "向用户提一个结构化问题并结束本段。需要澄清主题、数量、风格或让用户确认下一步时使用。",
        {
            "question": _STR,
            "options": {"type": "array", "items": {"type": "string"}},
            "allow_free_text": _BOOL,
        },
        ["question"],
    ),
    _fn(
        "load_skill",
        "读取一个技能的完整说明。先看系统提示里的技能目录再调用。",
        {"name": _STR},
        ["name"],
    ),
    _fn(
        "read_skill_file",
        "读取技能包内任意文本文件，例如 references/ 或 scripts/。",
        {"name": _STR, "path": _STR},
        ["name", "path"],
    ),
    _fn(
        "list_skill_files",
        "列出技能包内全部文件（references、scripts、assets 等）。",
        {"name": _STR},
        ["name"],
    ),
    _fn(
        "run_skill_script",
        "运行技能包 scripts/ 目录内的脚本。执行前会经过安全确认，输出会被截断。",
        {
            "name": _STR,
            "script": _STR,
            "args": {"type": "array", "items": _STR},
            "timeout": _INT,
        },
        ["name", "script"],
    ),
    _fn(
        "save_skill",
        "把用户确认过的技能保存到用户技能目录。只写 SKILL.md 正文。",
        {"name": _STR, "description": _STR, "content": _STR},
        ["name", "description", "content"],
    ),
    _fn(
        "save_skill_file",
        "在已有用户技能包内写入一个文本文件，例如 references/、assets/ 或 scripts/。执行前会经过安全确认。",
        {"name": _STR, "path": _STR, "content": _STR},
        ["name", "path", "content"],
    ),
    _fn(
        "update_session_state",
        "记录当前技能进度和已确认内容。刷新后据此继续，不要重复已完成的步骤。",
        {"state": _OBJ, "merge": _BOOL},
        ["state"],
    ),
    _fn(
        "list_assets",
        "列出资源库资产。可用于找参考图、角色图和已有成品。",
        {"kind": _STR, "include_hidden": _BOOL, "limit": _INT},
    ),
    _fn(
        "get_asset",
        "读取一个资产的完整信息。probe_media=true 时额外读取图片宽高或视频/音频时长。",
        {"asset_id": _INT, "probe_media": _BOOL},
        ["asset_id"],
    ),
    _fn("read_asset_text", "读取文本资产的正文。", {"asset_id": _INT}, ["asset_id"]),
    _fn(
        "list_characters",
        "列出角色库：外观、各视角图片、绑定音色。",
    ),
    _fn(
        "list_canvas_menu",
        "列出画布菜单设置：节点项、是否启用、媒体槽、可用工作流和默认工作流。"
        "给 menu_id 时只返回该项并带完整目标信息。",
        {"menu_id": _STR},
    ),
    _fn(
        "list_workflows",
        "列出工作流包。给 name 时返回完整输入参数规格；可按 capability 过滤。",
        {"name": _STR, "capability": _STR},
    ),
    _fn(
        "list_execution_specs",
        "列出已启用的工作流和云端模型执行契约，可按细分能力或类别过滤。",
        {"sub_capability": _STR, "category": _STR},
    ),
    _fn("list_voices", "列出音色库：音色名、服务商、是否默认、参考音频。"),
    _fn("list_music", "列出背景音乐库文件名，供节点 bgmPath 使用。", {"probe": _BOOL}),
    _fn(
        "generate_image",
        "提交文生图任务并等待结果。占用 GPU，调用前必须得到用户确认。",
        {
            "prompt": _STR,
            "provider_id": _INT,
            "model": _STR,
            "workflow": _STR,
            "size": _STR,
            "n": _INT,
        },
        ["prompt"],
    ),
    _fn(
        "edit_image",
        "提交图生图/编辑任务。需要图片资产 id。占用 GPU，调用前必须得到用户确认。",
        {
            "prompt": _STR,
            "asset_ids": {"type": "array", "items": _INT},
            "provider_id": _INT,
            "model": _STR,
            "workflow": _STR,
            "size": _STR,
        },
        ["prompt", "asset_ids"],
    ),
    _fn(
        "generate_video",
        "提交图生视频任务。需要首帧图片资产 id 和工作流包名。占用 GPU，调用前必须确认。",
        {
            "prompt": _STR,
            "asset_ids": {"type": "array", "items": _INT},
            "provider_id": _INT,
            "workflow": _STR,
            "model": _STR,
        },
        ["prompt", "workflow"],
    ),
    _fn(
        "tts",
        "文字转语音。占用 GPU 时可先确认。",
        {
            "text": _STR,
            "voice": _STR,
            "provider_id": _INT,
            "model": _STR,
            "workflow": _STR,
            "format": _STR,
        },
        ["text"],
    ),
    _fn(
        "asr",
        "把音频资产转成文字。",
        {"asset_id": _INT, "language": _STR, "provider_id": _INT},
        ["asset_id"],
    ),
    _fn(
        "create_character",
        "创建角色并生成四段式定妆照。占用 GPU，调用前必须得到用户确认。",
        {
            "name": _STR,
            "description": _STR,
            "tags": {"type": "array", "items": _STR},
            "ref_asset_ids": {"type": "array", "items": _INT},
            "provider_id": _INT,
            "workflow": _STR,
        },
        ["name", "description"],
    ),
    _fn("canvas_get_graph", "读取当前画布全部节点和连线。"),
    _fn("canvas_get_node", "读取一个画布的完整配置。", {"node_id": _STR}, ["node_id"]),
    _fn(
        "canvas_get_node_schema",
        "读取节点当前数据、执行目标、输入槽和可编辑参数规格。"
        "调整属性面板参数前先用它，避免猜字段名和范围。",
        {"node_id": _STR},
        ["node_id"],
    ),
    _fn(
        "canvas_add_node",
        "在画布上加节点。kind 为 input/function/concat/speech；"
        "文字转语音、语音转文字、音色替换都用 speech，并在 data.mode 写 tts、asr 或 vc；"
        "也可以用 kind=vc 作为音色替换别名。"
        "media_kind 为 image/video/audio/text/character。"
        "function 节点先建空白节点，不要传 pack；之后用 canvas_apply_menu 或 canvas_apply_pack 绑定执行目标。"
        "data 是初始字段，例如 input 文本节点的 text、varName。",
        {
            "kind": {
                "type": "string",
                "enum": ["input", "function", "concat", "speech", "vc"],
            },
            "media_kind": {
                "type": "string",
                "enum": ["image", "video", "audio", "text", "character"],
            },
            "x": {"type": "number"},
            "y": {"type": "number"},
            "group": _STR,
            "mediaKind": _STR,
            "data": _OBJ,
        },
        ["kind"],
    ),
    _fn(
        "canvas_apply_menu",
        "给空白功能节点或空白语音节点做首次功能绑定（优先）。先用 list_canvas_menu 找 menu_id；"
        "功能在创建时确定：已有 presetId 的节点不能再换功能，语音节点也不能换 mode，需要换功能时新建节点。"
        "已有上游时用 bindings 传槽位→变量名，避免自动补建空输入节点。没有合适菜单时再用 canvas_apply_pack。",
        {"node_id": _STR, "menu_id": _STR, "data": _OBJ, "bindings": _OBJ},
        ["node_id", "menu_id"],
    ),
    _fn(
        "canvas_apply_pack",
        "没有合适功能菜单时，把工作流包绑定到空白功能节点；这样得到没有 presetId 的通用节点。"
        "已有功能节点只能换当前功能允许的工作流，不能跨功能。先用 list_workflows 找包名。",
        {"node_id": _STR, "pack": _STR, "data": _OBJ, "bindings": _OBJ},
        ["node_id", "pack"],
    ),
    _fn(
        "canvas_update_node",
        "修改节点数据。patch 是节点 data 的部分字段，例如 prompt、varName、text、values。"
        "input 节点可用 patch.assetId 绑定资源，assetName 同步写。"
        "语音节点可写 voiceRecordId、providerId、model、separateBgm、subtitleAssetId、"
        "burnSubtitles、subtitleSize、subtitleColor、format，但不能改 mode。"
        "功能节点的 pack/outputKind 由 canvas_apply_menu 或 canvas_apply_pack 设置，不要直接改。",
        {"node_id": _STR, "patch": _OBJ},
        ["node_id", "patch"],
    ),
    _fn("canvas_connect", "连接两个节点。", {"source": _STR, "target": _STR}, ["source", "target"]),
    _fn(
        "canvas_disconnect",
        "断开连线。可给 edge_id，或给 source+target。",
        {"edge_id": _STR, "source": _STR, "target": _STR},
    ),
    _fn(
        "canvas_set_binding",
        "设置功能节点某个输入槽绑定的上游变量。",
        {"node_id": _STR, "slot": _STR, "source": _STR},
        ["node_id", "slot", "source"],
    ),
    _fn("canvas_layout", "自动整理画布布局。"),
    _fn(
        "canvas_delete_nodes",
        "删除节点和相连的边。执行前必须得到用户确认。",
        {"node_ids": _ARR},
        ["node_ids"],
    ),
    _fn(
        "canvas_run_nodes",
        "保存画布并执行当前节点。node_ids 只传当前要执行的节点，不要传上游；"
        "上游默认复用缓存，只会重跑选中的节点。"
        "force=true 时强制选中节点及其上游，代价更高；执行前由用户确认是否强制。",
        {"node_ids": _ARR, "force": _BOOL},
        ["node_ids"],
    ),
]


def is_client_tool(name: str) -> bool:
    return name in CLIENT_TOOL_NAMES


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _asset_rows(
    db: Session, owner_id: int, include_hidden: bool, kind: str, limit: int
) -> list[Asset]:
    stmt = select(Asset).where(Asset.owner_id == owner_id, Asset.origin != "character")
    if not include_hidden:
        stmt = stmt.where(Asset.hidden.is_(False))
    if kind:
        stmt = stmt.where(Asset.kind == kind)
    stmt = stmt.order_by(Asset.id.desc()).limit(max(1, min(limit, 100)))
    return list(db.scalars(stmt).all())


def _asset_brief(asset: Asset) -> dict[str, Any]:
    meta = asset.meta or {}
    return {
        "id": asset.id,
        "kind": asset.kind,
        "path": asset.path,
        "mime": asset.mime,
        "size": asset.size,
        "hidden": asset.hidden,
        "origin": asset.origin,
        "job_id": asset.job_id,
        "name": meta.get("source_name") or meta.get("name") or asset.path,
        "meta": meta,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


async def _asset_media_probe(asset: Asset) -> dict[str, Any]:
    path = resolve(asset.path)
    try:
        if asset.kind == "image":
            with Image.open(path) as image:
                return {"width": image.width, "height": image.height}
        if asset.kind in ("audio", "video"):
            data: dict[str, Any] = {"duration_s": round(await ffmpeg.probe_duration(path), 3)}
            if asset.kind == "video":
                width, height = await ffmpeg.probe_video_size(path)
                data.update({"width": width, "height": height})
            return data
    except (OSError, ProviderError) as exc:
        return {"error": str(exc)}
    return {}


def _workflow_summary(pack: Any) -> dict[str, Any]:
    return {
        "name": pack.name,
        "capability": pack.capability,
        "description": pack.description,
        "source": pack.source,
        "fps": pack.fps,
        "input_keys": list((pack.inputs or {}).keys()),
        "has_accel": bool(pack.accel),
    }


def _workflow_detail(pack: Any) -> dict[str, Any]:
    return {
        "name": pack.name,
        "capability": pack.capability,
        "description": pack.description,
        "source": pack.source,
        "fps": pack.fps,
        "inputs": pack.inputs or {},
        "outputs": pack.outputs or {},
        "requirements": pack.requirements or {},
        "accel": pack.accel or {},
        "llm_note": (pack.llm_note or "")[:4000],
    }


def _voice_brief(voice: Voice, provider_name: str = "") -> dict[str, Any]:
    return {
        "id": voice.id,
        "name": voice.name,
        "provider_id": voice.provider_id,
        "provider_name": provider_name,
        "voice_id": voice.voice_id,
        "ref_text": voice.ref_text,
        "tags": voice.tags or [],
        "is_default": voice.is_default,
        "has_ref_audio": bool(voice.ref_audio_path),
        "created_at": voice.created_at.isoformat() if voice.created_at else None,
    }


def _job_brief(job: Job) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "outputs": job.outputs or [],
        "error": job.error,
    }


async def _wait_job(db: Session, job: Job, *, timeout: float = 900.0) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while job.status in ("pending", "running"):
        if loop.time() > deadline:
            return {"job_id": job.id, "status": "timeout", "error": "任务等待超时"}
        await asyncio.sleep(0.8)
        db.expire(job)
        db.refresh(job)
    return _job_brief(job)


async def _submit(
    db: Session,
    jobs: Any,
    *,
    owner_id: int,
    kind: str,
    params: dict[str, Any],
    provider_id: int | None = None,
    model: str | None = None,
) -> Job:
    if jobs is None:
        raise RuntimeError("任务队列未启动")
    return jobs.submit(
        db,
        owner_id=owner_id,
        kind=kind,
        params=params,
        provider_id=provider_id,
        model=model,
    )


async def run_server_tool(
    db: Session,
    session: AgentSession,
    user: User,
    jobs: Any,
    name: str,
    raw_arguments: Any,
) -> AsyncIterator[dict[str, Any]]:
    """执行一个服务端工具。最后一项是 {"event":"tool_result","data": result}。"""
    args = _parse_arguments(raw_arguments)

    def result(data: Any) -> dict[str, Any]:
        return {"event": "tool_result", "data": data}

    if name == "ask_user":
        yield result(
            {
                "question": str(args.get("question") or ""),
                "options": [str(item) for item in (args.get("options") or [])],
                "allow_free_text": bool(args.get("allow_free_text", True)),
            }
        )
        return
    if name == "load_skill":
        skill_name = str(args.get("name") or "")
        meta, body = read_skill(skill_name)
        session.active_skill = skill_name
        db.commit()
        yield result({"name": meta["name"], "description": meta["description"], "body": body})
        return
    if name == "read_skill_file":
        text = read_skill_file(str(args.get("name") or ""), str(args.get("path") or ""))
        yield result({"content": text[:60_000]})
        return
    if name == "list_skill_files":
        files = list_skill_files(str(args.get("name") or ""))
        yield result({"files": files})
        return
    if name == "run_skill_script":
        output = await run_skill_script(
            str(args.get("name") or ""),
            str(args.get("script") or ""),
            [str(item) for item in (args.get("args") or [])],
            timeout=int(args.get("timeout") or 60),
        )
        yield result(output)
        return
    if name == "update_session_state":
        incoming = args.get("state")
        if not isinstance(incoming, dict):
            incoming = {
                key: value for key, value in args.items() if key not in {"state", "merge"}
            }
        old = dict(session.skill_state or {})
        state = {**old, **incoming} if bool(args.get("merge", True)) else dict(incoming)
        for key in ("pending", "queued_client", "safety"):
            if key in old:
                state[key] = old[key]
        session.skill_state = state
        db.commit()
        yield result(
            {
                "skill_state": {
                    key: value
                    for key, value in state.items()
                    if key not in {"pending", "queued_client"}
                }
            }
        )
        return
    if name == "save_skill":
        saved = save_skill_text(
            str(args.get("name") or ""),
            str(args.get("description") or ""),
            str(args.get("content") or ""),
        )
        yield result({"name": saved, "saved": True})
        return
    if name == "save_skill_file":
        saved = save_skill_file(
            str(args.get("name") or ""),
            str(args.get("path") or ""),
            str(args.get("content") or ""),
        )
        yield result({"name": str(args.get("name") or ""), "path": saved, "saved": True})
        return
    if name == "list_assets":
        rows = _asset_rows(
            db,
            user.id,
            bool(args.get("include_hidden", False)),
            str(args.get("kind") or ""),
            int(args.get("limit") or 30),
        )
        yield result({"assets": [_asset_brief(row) for row in rows]})
        return
    if name == "get_asset":
        asset = db.get(Asset, int(args.get("asset_id") or 0))
        if asset is None or asset.owner_id != user.id:
            yield result({"error": "资产不存在"})
            return
        data = _asset_brief(asset)
        if bool(args.get("probe_media", False)):
            data["media"] = await _asset_media_probe(asset)
        yield result({"asset": data})
        return
    if name == "read_asset_text":
        asset = db.get(Asset, int(args.get("asset_id") or 0))
        if asset is None or asset.owner_id != user.id:
            yield result({"error": "资产不存在"})
            return
        try:
            text = resolve(asset.path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            yield result({"error": str(exc)})
            return
        yield result({"asset_id": asset.id, "content": text[:60_000]})
        return
    if name == "list_characters":
        rows = db.scalars(
            select(Character).where(Character.owner_id == user.id).order_by(Character.id)
        ).all()
        yield result(
            {
                "characters": [
                    {
                        "id": row.id,
                        "name": row.name,
                        "description": row.description,
                        "tags": row.tags or [],
                        "views": {
                            "portrait": row.portrait_path,
                            "turnaround": row.turnaround_path,
                            "front": row.front_path,
                            "side": row.side_path,
                            "back": row.back_path,
                        },
                        "voice_record_id": row.voice_record_id,
                        "voice_name": row.voice_name,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                    for row in rows
                ]
            }
        )
        return
    if name == "list_canvas_menu":
        items = resolve_menu_items(db, user.id)
        wanted = str(args.get("menu_id") or "")
        if wanted:
            items = [
                item
                for item in items
                if item.get("id") == wanted or item.get("sub_capability") == wanted
            ]
        yield result({"items": items})
        return
    if name == "list_workflows":
        packs = list_packs(str(args.get("capability") or "") or None)
        wanted = str(args.get("name") or "")
        if wanted:
            pack = next((item for item in packs if item.name == wanted), None)
            if pack is None:
                yield result({"error": f"工作流包不存在: {wanted}"})
                return
            yield result({"workflow": _workflow_detail(pack)})
            return
        yield result({"workflows": [_workflow_summary(pack) for pack in packs]})
        return
    if name == "list_execution_specs":
        from liberastra.providers.schema_registry import model_specs, workflow_specs

        specs = workflow_specs(list_packs())
        providers = db.scalars(
            select(Provider).where(Provider.owner_id == user.id, Provider.enabled.is_(True))
        ).all()
        for record in providers:
            specs.extend(model_specs(record))
        sub = str(args.get("sub_capability") or "")
        category = str(args.get("category") or "")
        rows = [
            spec.to_dict()
            for spec in specs
            if (not sub or spec.sub_capability == sub)
            and (not category or spec.category == category)
        ]
        yield result({"specs": rows})
        return
    if name == "list_voices":
        rows = db.scalars(
            select(Voice).where(Voice.owner_id == user.id).order_by(Voice.id)
        ).all()
        provider_names = {
            record.id: record.name
            for record in db.scalars(
                select(Provider).where(Provider.owner_id == user.id)
            ).all()
        }
        yield result(
            {
                "voices": [
                    _voice_brief(row, provider_names.get(row.provider_id or 0, ""))
                    for row in rows
                ]
            }
        )
        return
    if name == "list_music":
        root = get_settings().data_dir / "bgm"
        allowed = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
        rows: list[dict[str, Any]] = []
        if root.exists():
            for path in sorted(root.iterdir()):
                if not path.is_file() or path.suffix.lower() not in allowed:
                    continue
                row: dict[str, Any] = {
                    "name": path.name,
                    "size": path.stat().st_size,
                    "path": f"bgm/{path.name}",
                }
                if bool(args.get("probe", False)):
                    try:
                        row["duration_s"] = round(await ffmpeg.probe_duration(path), 3)
                    except ProviderError as exc:
                        row["error"] = str(exc)
                rows.append(row)
        yield result({"music": rows})
        return
    if name == "generate_image":
        provider = pick_provider(db, "image", args.get("provider_id"))
        workflow = str(args.get("workflow") or "")
        if provider.type == "comfyui" and not workflow:
            yield result({"error": "ComfyUI 类型需要 workflow 参数"})
            return
        prompt = str(args.get("prompt") or "")
        job = await _submit(
            db,
            jobs,
            owner_id=user.id,
            kind="image.generate",
            params={
                "workflow": workflow,
                "prompt": prompt,
                "size": str(args.get("size") or "1024x1024"),
                "n": int(args.get("n") or 1),
                "inputs": {"prompt": prompt},
            },
            provider_id=provider.id,
            model=args.get("model"),
        )
        yield {"event": "tool_progress", "data": {"job_id": job.id, "status": job.status}}
        yield result(await _wait_job(db, job))
        return
    if name == "edit_image":
        provider = pick_provider(db, "image", args.get("provider_id"))
        asset_ids = [int(item) for item in (args.get("asset_ids") or [])]
        rows = [db.get(Asset, aid) for aid in asset_ids]
        paths = [row.path for row in rows if row is not None and row.owner_id == user.id]
        if not paths:
            yield result({"error": "没有可用的输入图片"})
            return
        prompt = str(args.get("prompt") or "")
        job = await _submit(
            db,
            jobs,
            owner_id=user.id,
            kind="image.edit",
            params={
                "workflow": str(args.get("workflow") or ""),
                "prompt": prompt,
                "image_paths": paths,
                "size": str(args.get("size") or "1024x1024"),
                "inputs": {"prompt": prompt},
            },
            provider_id=provider.id,
            model=args.get("model"),
        )
        yield {"event": "tool_progress", "data": {"job_id": job.id, "status": job.status}}
        yield result(await _wait_job(db, job))
        return
    if name == "generate_video":
        workflow = str(args.get("workflow") or "")
        if not workflow:
            yield result({"error": "generate_video 需要 workflow（工作流包名）"})
            return
        asset_ids = [int(item) for item in (args.get("asset_ids") or [])]
        rows = [db.get(Asset, aid) for aid in asset_ids]
        paths = [row.path for row in rows if row is not None and row.owner_id == user.id]
        provider = pick_provider(db, "video", args.get("provider_id"))
        job = await _submit(
            db,
            jobs,
            owner_id=user.id,
            kind="video.i2v",
            params={
                "workflow": workflow,
                "prompt": str(args.get("prompt") or ""),
                "image_paths": paths,
            },
            provider_id=provider.id,
            model=args.get("model"),
        )
        yield {"event": "tool_progress", "data": {"job_id": job.id, "status": job.status}}
        yield result(await _wait_job(db, job))
        return
    if name == "tts":
        provider = pick_provider(db, "tts", args.get("provider_id"))
        job = await _submit(
            db,
            jobs,
            owner_id=user.id,
            kind="tts.synthesize",
            params={
                "text": str(args.get("text") or ""),
                "voice": str(args.get("voice") or ""),
                "format": str(args.get("format") or "mp3"),
                "workflow": str(args.get("workflow") or ""),
                "options": {},
            },
            provider_id=provider.id,
            model=args.get("model"),
        )
        yield {"event": "tool_progress", "data": {"job_id": job.id, "status": job.status}}
        yield result(await _wait_job(db, job))
        return
    if name == "asr":
        asset = db.get(Asset, int(args.get("asset_id") or 0))
        if asset is None or asset.owner_id != user.id:
            yield result({"error": "音频资产不存在"})
            return
        provider = pick_provider(db, "asr", args.get("provider_id"))
        job = await _submit(
            db,
            jobs,
            owner_id=user.id,
            kind="asr.transcribe",
            params={
                "file_path": asset.path,
                "language": args.get("language"),
                "task": "transcribe",
            },
            provider_id=provider.id,
        )
        yield {"event": "tool_progress", "data": {"job_id": job.id, "status": job.status}}
        yield result(await _wait_job(db, job))
        return
    if name == "create_character":
        character_name = str(args.get("name") or "").strip()
        if not character_name:
            yield result({"error": "create_character 需要 name"})
            return
        if jobs is None:
            yield result({"error": "任务队列未启动，无法生成角色定妆照"})
            return
        description = str(args.get("description") or character_name)[:2000]
        character = Character(
            owner_id=user.id,
            name=character_name[:128],
            description=description,
            tags=[str(item) for item in (args.get("tags") or [])][:20],
        )
        db.add(character)
        db.commit()
        db.refresh(character)
        asset_ids = [int(item) for item in (args.get("ref_asset_ids") or [])]
        ref_paths = [
            row.path
            for row in (db.get(Asset, aid) for aid in asset_ids)
            if row is not None and row.owner_id == user.id
        ]
        provider = pick_provider(db, "image", args.get("provider_id"))
        job = await _submit(
            db,
            jobs,
            owner_id=user.id,
            kind="character.generate",
            params={
                "character_id": character.id,
                "description": description,
                "prompt": description,
                "t2i_workflow": str(args.get("workflow") or ""),
                "ref_image_paths": ref_paths,
            },
            provider_id=provider.id,
        )
        yield {"event": "tool_progress", "data": {"job_id": job.id, "status": job.status}}
        outcome = await _wait_job(db, job)
        yield result(
            {
                "character_id": character.id,
                "name": character.name,
                "job": outcome,
            }
        )
        return
    yield result({"error": f"未知工具: {name}"})


def ensure_agent_llm(db: Session, provider_id: int | None, model: str) -> tuple[Any, str]:
    """沿用系统设置里的默认 LLM；会话里显式指定的优先。"""
    return pick_llm_with_model(db, provider_id, model)


__all__ = [
    "TOOL_SCHEMAS",
    "CLIENT_TOOL_NAMES",
    "ensure_agent_llm",
    "is_client_tool",
    "run_server_tool",
]
