"""导演台会话、SSE 对话和技能管理。"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sse_starlette import EventSourceResponse

from liberastra.agent.context import assemble_user_content
from liberastra.agent.runtime import (
    apply_tool_results,
    cancel_pending,
    caps_for,
    iter_turn,
    request_cancel,
    run_approved,
)
from liberastra.agent.safety import policy_view, remember_auto
from liberastra.agent.skills import (
    BUILTIN_NAMES,
    MAX_TOTAL_BYTES,
    SkillError,
    files_from_zip,
    list_skill_files,
    list_skill_summaries,
    read_skill,
    save_skill_files,
    skill_dir,
)
from liberastra.api.deps import CurrentUser, DbSession
from liberastra.models import AgentMessage, AgentSession, AgentSkill
from liberastra.services.providers import build_adapter, pick_llm_with_model

router = APIRouter(prefix="/agent", tags=["agent"])


class SessionIn(BaseModel):
    canvas_id: str | None = None
    title: str | None = None
    provider_id: int | None = None
    model: str = ""
    active_skill: str = ""


class SessionPatch(BaseModel):
    title: str | None = None
    provider_id: int | None = None
    model: str | None = None
    active_skill: str | None = None
    use_default: bool | None = None


class TurnIn(BaseModel):
    text: str = ""
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    refs: list[dict[str, Any]] = Field(default_factory=list)
    provider_id: int | None = None
    model: str = ""
    active_skill: str | None = None


class ToolResultsIn(BaseModel):
    results: list[dict[str, Any]] = Field(default_factory=list)
    approved: bool | None = None
    remember: bool = False


def _owned(db, user, session_id: str) -> AgentSession:  # noqa: ANN001
    row = db.get(AgentSession, session_id)
    if row is None or row.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return row


def _mark_cancelled(db, row: AgentSession) -> None:  # noqa: ANN001
    cancel_pending(db, row, "连接断开，操作已取消")


def _session_out(row: AgentSession) -> dict[str, Any]:
    return {
        "id": row.id,
        "canvas_id": row.canvas_id,
        "title": row.title,
        "provider_id": row.provider_id,
        "model": row.model,
        "active_skill": row.active_skill,
        "skill_state": row.skill_state or {},
        "status": row.status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("/sessions")
def list_sessions(user: CurrentUser, db: DbSession, canvas_id: str | None = None) -> list[dict]:
    stmt = select(AgentSession).where(AgentSession.owner_id == user.id)
    if canvas_id:
        stmt = stmt.where(AgentSession.canvas_id == canvas_id)
    rows = db.scalars(stmt.order_by(AgentSession.updated_at.desc()).limit(50)).all()
    return [_session_out(row) for row in rows]


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(body: SessionIn, user: CurrentUser, db: DbSession) -> dict:
    provider, model = pick_llm_with_model(db, body.provider_id, body.model)
    row = AgentSession(
        owner_id=user.id,
        canvas_id=body.canvas_id,
        title=(body.title or "").strip() or "新对话",
        provider_id=provider.id,
        model=model,
        active_skill=body.active_skill,
        skill_state={},
        status="idle",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _session_out(row)


@router.patch("/sessions/{session_id}")
def patch_session(
    session_id: str, body: SessionPatch, user: CurrentUser, db: DbSession
) -> dict:
    row = _owned(db, user, session_id)
    if body.title is not None:
        row.title = body.title.strip() or row.title
    if body.active_skill is not None:
        row.active_skill = body.active_skill
    if body.use_default:
        provider, model = pick_llm_with_model(db, None, "")
        row.provider_id = provider.id
        row.model = model
    elif body.provider_id is not None or body.model is not None:
        provider, model = pick_llm_with_model(
            db,
            body.provider_id if body.provider_id is not None else row.provider_id,
            body.model if body.model is not None else (row.model or ""),
        )
        row.provider_id = provider.id
        row.model = model
    db.commit()
    db.refresh(row)
    return _session_out(row)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, user: CurrentUser, db: DbSession) -> None:
    row = _owned(db, user, session_id)
    db.delete(row)
    db.commit()


@router.get("/sessions/{session_id}/messages")
def list_messages(session_id: str, user: CurrentUser, db: DbSession) -> list[dict]:
    row = _owned(db, user, session_id)
    return [
        {
            "id": item.id,
            "role": item.role,
            "content": item.content,
            "created_at": item.created_at,
        }
        for item in row.messages
    ]


def _sse(events: AsyncIterator[dict[str, Any]]) -> EventSourceResponse:
    async def stream() -> AsyncIterator[dict[str, Any]]:
        async for event in events:
            payload = json.dumps(event["data"], ensure_ascii=False, default=str)
            yield {"event": event["event"], "data": payload}

    return EventSourceResponse(stream())


@router.post("/sessions/{session_id}/turns")
async def turn(
    session_id: str,
    body: TurnIn,
    user: CurrentUser,
    db: DbSession,
    request: Request,
) -> EventSourceResponse:
    row = _owned(db, user, session_id)
    if row.status in {"running", "awaiting_client", "awaiting_confirm"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="会话还在等待上一步"
        )
    if body.active_skill is not None:
        row.active_skill = body.active_skill
    provider, model = pick_llm_with_model(
        db,
        body.provider_id if body.provider_id else row.provider_id,
        body.model if body.model else (row.model or ""),
    )
    row.provider_id = provider.id
    row.model = model
    caps = caps_for(provider, model)
    payload = {"text": body.text, "attachments": body.attachments, "refs": body.refs}
    assemble_user_content(db, user.id, payload, vision=caps["vision"])
    db.add(AgentMessage(session_id=row.id, role="user", content=payload))
    if body.text and row.title == "新对话":
        row.title = body.text.strip()[:32] or row.title
    db.commit()
    db.refresh(row)
    adapter = build_adapter(provider)

    async def events() -> AsyncIterator[dict[str, Any]]:
        async for event in iter_turn(
            db,
            row,
            user,
            adapter,
            request.app.state.jobs,
            native_tools=caps["tools"],
            vision=caps["vision"],
        ):
            if await request.is_disconnected():
                request_cancel(row.id)
                _mark_cancelled(db, row)
                return
            yield event

    return _sse(events())


@router.post("/sessions/{session_id}/tool-results")
async def tool_results(
    session_id: str,
    body: ToolResultsIn,
    user: CurrentUser,
    db: DbSession,
    request: Request,
) -> EventSourceResponse:
    row = _owned(db, user, session_id)
    if row.status not in {"awaiting_client", "awaiting_confirm"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="会话不在等待工具结果"
        )
    state = dict(row.skill_state or {})
    queued = state.get("queued_client") or {}
    calls = list(state.get("pending") or []) + list(queued.get("calls") or [])
    if body.remember and body.approved is not False and calls:
        remember_auto(row, [str(call.get("name") or "") for call in calls])
        db.commit()
    if body.approved is False and not body.results:
        body.results = [
            {
                "tool_call_id": call.get("id"),
                "name": call.get("name"),
                "result": {"error": "用户拒绝了该操作"},
            }
            for call in calls
        ]
        state.pop("pending", None)
        state.pop("queued_client", None)
        row.skill_state = state
        db.commit()
    apply_tool_results(db, row, body.results, approved=body.approved)
    db.refresh(row)
    provider, _model = pick_llm_with_model(db, row.provider_id, row.model or "")
    caps = caps_for(provider, row.model or "")
    adapter = build_adapter(provider)

    async def events() -> AsyncIterator[dict[str, Any]]:
        if body.approved:
            async for event in run_approved(db, row, user, request.app.state.jobs):
                yield event
        async for event in iter_turn(
            db,
            row,
            user,
            adapter,
            request.app.state.jobs,
            native_tools=caps["tools"],
            vision=caps["vision"],
        ):
            if await request.is_disconnected():
                request_cancel(row.id)
                _mark_cancelled(db, row)
                return
            yield event

    return _sse(events())


@router.post("/sessions/{session_id}/cancel")
def cancel(session_id: str, user: CurrentUser, db: DbSession) -> dict:
    row = _owned(db, user, session_id)
    request_cancel(row.id)
    cancel_pending(db, row)
    return {"ok": True}


@router.get("/sessions/{session_id}/safety")
def session_safety(session_id: str, user: CurrentUser, db: DbSession) -> dict:
    row = _owned(db, user, session_id)
    return policy_view(row)


@router.get("/skills")
def skills(user: CurrentUser, db: DbSession) -> list[dict]:
    return list_skill_summaries(db, user.id)


@router.get("/skills/{name}")
def skill_detail(name: str, user: CurrentUser, db: DbSession) -> dict:
    del user, db
    try:
        meta, body = read_skill(name)
        files = list_skill_files(name)
    except SkillError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "name": meta.get("name"),
        "description": meta.get("description"),
        "body": body,
        "license": meta.get("license", ""),
        "compatibility": meta.get("compatibility", ""),
        "allowed_tools": meta.get("allowed_tools", []),
        "files": files,
    }


@router.post("/skills", status_code=status.HTTP_201_CREATED)
async def upload_skill(file: UploadFile, user: CurrentUser, db: DbSession) -> dict:
    payload = await file.read(MAX_TOTAL_BYTES + 1)
    if len(payload) > MAX_TOTAL_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="技能包总大小超过 2MB"
        )
    filename = (file.filename or "").lower()
    try:
        if filename.endswith(".zip"):
            files = files_from_zip(payload)
        elif filename.endswith(".md"):
            files = {"SKILL.md": payload}
        else:
            raise SkillError("只接受 SKILL.md 或 zip")
        name = save_skill_files(files)
    except SkillError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    row = db.scalar(
        select(AgentSkill).where(AgentSkill.owner_id == user.id, AgentSkill.name == name)
    )
    if row is None:
        db.add(
            AgentSkill(
                owner_id=user.id,
                name=name,
                source="user",
                enabled=True,
                version=1,
            )
        )
    else:
        row.version += 1
    db.commit()
    return {"name": name}


@router.post("/skills/{name}/enabled")
def set_enabled(
    name: str, user: CurrentUser, db: DbSession, enabled: bool = True
) -> dict:
    row = db.scalar(
        select(AgentSkill).where(AgentSkill.owner_id == user.id, AgentSkill.name == name)
    )
    if row is None:
        if name not in BUILTIN_NAMES and skill_dir(name, user_only=True) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="技能不存在")
        row = AgentSkill(
            owner_id=user.id,
            name=name,
            source="builtin" if name in BUILTIN_NAMES else "user",
            enabled=enabled,
            version=1,
        )
        db.add(row)
    else:
        row.enabled = enabled
    db.commit()
    return {"name": name, "enabled": enabled}


@router.delete("/skills/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(name: str, user: CurrentUser, db: DbSession) -> None:
    if name in BUILTIN_NAMES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除内置技能")
    folder = skill_dir(name, user_only=True)
    if folder is not None:
        for child in sorted(folder.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
        for child in sorted(folder.rglob("*"), reverse=True):
            if child.is_dir():
                child.rmdir()
        folder.rmdir()
    row = db.scalar(
        select(AgentSkill).where(AgentSkill.owner_id == user.id, AgentSkill.name == name)
    )
    if row is not None:
        db.delete(row)
        db.commit()


@router.get("/skills/{name}/export")
def export_skill(name: str, user: CurrentUser, db: DbSession):  # noqa: ANN201
    del user, db
    folder = skill_dir(name)
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="技能不存在")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in folder.rglob("*"):
            if path.is_file():
                archive.write(path, f"{name}/{path.relative_to(folder).as_posix()}")
    from fastapi.responses import Response

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}.zip"'},
    )
