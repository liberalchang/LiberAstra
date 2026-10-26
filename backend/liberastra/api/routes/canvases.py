"""画布路由：画布 CRUD / 复制、工作流包分组（所属）、执行编排。"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.models import AppSetting, Asset, Canvas, CanvasNodeRun, User, utcnow
from liberastra.providers.base import ProviderError
from liberastra.schemas.canvas import (
    CanvasCreateIn,
    CanvasGraphIn,
    CanvasListOut,
    CanvasNodeRunOut,
    CanvasOut,
    CanvasRunIn,
    CanvasRunOut,
    CanvasUpdateIn,
)
from liberastra.services import canvas_run
from liberastra.services.canvas_graph import detect_cycle
from liberastra.services.workflows import list_packs

router = APIRouter(prefix="/canvases", tags=["canvases"])

GROUPS_SETTING_KEY = "canvas_workflow_groups"

# 工作流包 capability → 默认分组名（首次读取分组配置时自动初始化）
DEFAULT_GROUP_NAMES = {
    "t2i": "文生图",
    "i2i": "图生图",
    "upscale": "放大修复",
    "t2v": "文生视频",
    "i2v": "图生视频",
    "avatar": "数字人",
    "motion": "动作迁移",
    "analysis": "画面分析",
}


def _get_owned(db, canvas_id: str, user: User) -> Canvas:  # noqa: ANN001
    record = db.get(Canvas, canvas_id)
    if record is None or record.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="画布不存在")
    return record


def _node_runs_out(db, canvas_id: str) -> list[CanvasNodeRunOut]:  # noqa: ANN001
    rows = db.scalars(
        select(CanvasNodeRun).where(CanvasNodeRun.canvas_id == canvas_id)
    ).all()
    out: list[CanvasNodeRunOut] = []
    for row in rows:
        asset_ids = [int(a) for a in (row.asset_ids or [])]
        published = bool(asset_ids) and all(
            not asset.hidden
            for aid in asset_ids
            if (asset := db.get(Asset, aid)) is not None
        )
        out.append(
            CanvasNodeRunOut(
                node_id=row.node_id,
                status=row.status,
                job_id=row.job_id,
                asset_ids=asset_ids,
                error=row.error,
                published=published,
            )
        )
    return out


def _canvas_out(db, record: Canvas) -> CanvasOut:  # noqa: ANN001
    return CanvasOut(
        id=record.id,
        name=record.name,
        graph=record.graph or {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
        created_at=record.created_at,
        updated_at=record.updated_at,
        node_runs=_node_runs_out(db, record.id),
    )


def _validate_graph(graph: CanvasGraphIn) -> None:
    node_ids = [n.id for n in graph.nodes]
    if len(set(node_ids)) != len(node_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="节点 id 重复")
    # 输出变量名是画布级命名空间:重名会让槽位绑定和提示词引用产生歧义
    var_names = [
        str(n.data.get("varName")).strip()
        for n in graph.nodes
        if str(n.data.get("varName") or "").strip()
    ]
    if len(set(var_names)) != len(var_names):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="节点输出变量名重复，请在属性面板改名"
        )
    known = set(node_ids)
    for edge in graph.edges:
        if edge.source not in known or edge.target not in known:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="存在指向未知节点的连线"
            )
        if edge.source == edge.target:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="节点不能连接自身"
            )
    cycle = detect_cycle(graph.model_dump())
    if cycle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"画布存在环形依赖（节点 {cycle}）"
        )


@router.get("", response_model=list[CanvasListOut])
def list_canvases(user: CurrentUser, db: DbSession) -> list[CanvasListOut]:
    records = db.scalars(
        select(Canvas).where(Canvas.owner_id == user.id).order_by(Canvas.updated_at.desc())
    ).all()
    return [
        CanvasListOut(
            id=r.id,
            name=r.name,
            node_count=len((r.graph or {}).get("nodes") or []),
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in records
    ]


@router.post("", response_model=CanvasOut, status_code=status.HTTP_201_CREATED)
def create_canvas(body: CanvasCreateIn, user: CurrentUser, db: DbSession) -> CanvasOut:
    graph = body.graph or CanvasGraphIn()
    _validate_graph(graph)
    record = Canvas(
        name=(body.name or "").strip() or "未命名画布",
        graph=graph.model_dump(),
        owner_id=user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _canvas_out(db, record)


@router.get("/groups")
def get_groups(user: CurrentUser, db: DbSession) -> dict[str, list[str]]:
    """工作流包分组（所属）。首次读取按 capability 自动初始化并持久化。"""
    row = db.get(AppSetting, GROUPS_SETTING_KEY)
    if row is not None:
        try:
            data = json.loads(row.value)
            if isinstance(data, dict):
                return {str(k): [str(p) for p in v] for k, v in data.items()}
        except json.JSONDecodeError:
            pass
    groups: dict[str, list[str]] = {}
    for pack in list_packs():
        group = DEFAULT_GROUP_NAMES.get(pack.capability, pack.capability)
        groups.setdefault(group, []).append(pack.name)
    db.add(AppSetting(key=GROUPS_SETTING_KEY, value=json.dumps(groups, ensure_ascii=False)))
    db.commit()
    return groups


@router.put("/groups")
def put_groups(body: dict[str, list[str]], user: CurrentUser, db: DbSession) -> dict[str, list[str]]:
    known = {pack.name for pack in list_packs()}
    cleaned: dict[str, list[str]] = {}
    for group, packs in body.items():
        name = str(group).strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分组名不能为空")
        cleaned[name] = [p for p in packs if p in known]
    row = db.get(AppSetting, GROUPS_SETTING_KEY)
    payload = json.dumps(cleaned, ensure_ascii=False)
    if row is None:
        db.add(AppSetting(key=GROUPS_SETTING_KEY, value=payload))
    else:
        row.value = payload
    db.commit()
    return cleaned


@router.get("/{canvas_id}", response_model=CanvasOut)
def get_canvas(canvas_id: str, user: CurrentUser, db: DbSession) -> CanvasOut:
    return _canvas_out(db, _get_owned(db, canvas_id, user))


@router.put("/{canvas_id}", response_model=CanvasOut)
def update_canvas(
    canvas_id: str, body: CanvasUpdateIn, user: CurrentUser, db: DbSession
) -> CanvasOut:
    record = _get_owned(db, canvas_id, user)
    if body.name is not None:
        record.name = body.name.strip() or record.name
    if body.graph is not None:
        _validate_graph(body.graph)
        record.graph = body.graph.model_dump()
    record.updated_at = utcnow()
    db.commit()
    db.refresh(record)
    return _canvas_out(db, record)


@router.post("/{canvas_id}/duplicate", response_model=CanvasOut, status_code=status.HTTP_201_CREATED)
def duplicate_canvas(canvas_id: str, user: CurrentUser, db: DbSession) -> CanvasOut:
    record = _get_owned(db, canvas_id, user)
    copy = Canvas(
        name=f"{record.name} 副本",
        graph=record.graph or {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
        owner_id=user.id,
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return _canvas_out(db, copy)


@router.delete("/{canvas_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_canvas(canvas_id: str, user: CurrentUser, db: DbSession) -> None:
    record = _get_owned(db, canvas_id, user)
    db.delete(record)
    db.commit()


@router.post("/{canvas_id}/run", response_model=CanvasRunOut, status_code=status.HTTP_202_ACCEPTED)
async def run_canvas(
    canvas_id: str, body: CanvasRunIn, user: CurrentUser, db: DbSession, request: Request
) -> CanvasRunOut:
    record = _get_owned(db, canvas_id, user)
    try:
        run_id, plan = canvas_run.start_run(
            request.app, record, user.id, body.node_ids, body.force_node_ids
        )
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CanvasRunOut(run_id=run_id, plan=plan)


@router.post(
    "/{canvas_id}/nodes/{node_id}/run",
    response_model=CanvasRunOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_canvas_node(
    canvas_id: str, node_id: str, user: CurrentUser, db: DbSession, request: Request
) -> CanvasRunOut:
    """强制重跑单个节点及其上游（忽略指纹复用）。"""
    record = _get_owned(db, canvas_id, user)
    try:
        run_id, plan = canvas_run.start_run(
            request.app, record, user.id, [node_id], [node_id]
        )
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CanvasRunOut(run_id=run_id, plan=plan)


@router.get("/{canvas_id}/runs", response_model=CanvasRunOut | None)
def get_latest_run(canvas_id: str, user: CurrentUser, db: DbSession, request: Request):  # noqa: ANN201
    """最近一次执行的实时 plan（内存）;没有进行中的执行时按持久化的节点记录合成。"""
    record = _get_owned(db, canvas_id, user)
    plan = canvas_run.latest_plan(request.app, record.id)
    if plan is not None:
        return CanvasRunOut(run_id="", plan=plan)
    rows = _node_runs_out(db, record.id)
    return CanvasRunOut(
        run_id="",
        plan=[
            {"node_id": r.node_id, "job_id": r.job_id, "status": r.status, "reused": False}
            for r in rows
        ],
    )
