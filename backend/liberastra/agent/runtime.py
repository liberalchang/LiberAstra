"""ReAct 循环：流式文本、工具分发、步数上限、取消和客户端工具队列。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from liberastra.agent.context import assemble_user_content
from liberastra.agent.protocol import parse_text_tool_calls
from liberastra.agent.safety import SafetyDecision, decide_tool
from liberastra.agent.tools import (
    TOOL_SCHEMAS,
    is_client_tool,
    run_server_tool,
)
from liberastra.agent.workspace import build_system_prompt
from liberastra.models import AgentMessage, AgentSession, User, utcnow
from liberastra.providers.catalog import model_caps

MAX_STEPS = 25
_CANCELS: set[str] = set()


def request_cancel(session_id: str) -> None:
    _CANCELS.add(str(session_id))


def _cancelled(session_id: str) -> bool:
    return str(session_id) in _CANCELS


def caps_for(provider: Any, model: str) -> dict[str, bool]:
    return model_caps(provider, model)


def _collapse_parts(parts: list[dict[str, Any]]) -> Any:
    if all(part.get("type") == "text" for part in parts):
        return "\n".join(str(part.get("text") or "") for part in parts).strip()
    return parts


def _history(db: Session, session: AgentSession, vision: bool) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for row in session.messages:
        content = row.content or {}
        if row.role == "user":
            try:
                parts = assemble_user_content(db, session.owner_id, content, vision=vision)
            except Exception as exc:  # noqa: BLE001 —— 历史附件失效时保留文字
                logger.warning("组装历史消息失败: {}", exc)
                parts = [{"type": "text", "text": str(content.get("text") or "")}]
            messages.append({"role": "user", "content": _collapse_parts(parts)})
        elif row.role == "assistant":
            text = str(content.get("text") or "")
            calls = content.get("tool_calls") or []
            if calls:
                message: dict[str, Any] = {
                    "role": "assistant",
                    "content": text,
                    "tool_calls": calls,
                }
                thought = content.get("reasoning_content")
                if isinstance(thought, str) and thought:
                    message["reasoning_content"] = thought
                messages.append(message)
            elif text:
                messages.append({"role": "assistant", "content": text})
        elif row.role == "tool":
            result = content.get("result")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(content.get("tool_call_id") or ""),
                    "content": result
                    if isinstance(result, str)
                    else json.dumps(result, ensure_ascii=False),
                }
            )
    return messages


def _save_assistant(
    db: Session,
    session: AgentSession,
    text: str,
    calls: list[dict[str, Any]],
    reasoning: str = "",
) -> None:
    if not text.strip() and not calls:
        return
    content: dict[str, Any] = {"text": text}
    if calls:
        content["tool_calls"] = calls
    if reasoning and calls:
        content["reasoning_content"] = reasoning
    db.add(AgentMessage(session_id=session.id, role="assistant", content=content))
    db.commit()


def _save_tool(db: Session, session: AgentSession, call_id: str, name: str, result: Any) -> None:
    ok = not (isinstance(result, dict) and result.get("error"))
    db.add(
        AgentMessage(
            session_id=session.id,
            role="tool",
            content={
                "tool_call_id": call_id,
                "name": name,
                "result": result,
                "ok": ok,
            },
        )
    )
    db.commit()


def _reject_calls(
    db: Session,
    session: AgentSession,
    calls: list[dict[str, Any]],
    reason: str,
) -> None:
    """暂停等待用户时，给同批未执行的调用补结果，保证下一轮消息完整。"""
    for call in calls:
        _save_tool(
            db,
            session,
            str(call["id"]),
            str(call["function"]["name"]),
            {"error": reason},
        )


def _normalize_calls(raw_calls: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for index, item in enumerate(raw_calls or []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if not name:
            continue
        arguments = item.get("arguments")
        calls.append(
            {
                "id": str(item.get("id") or f"call_{index}"),
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": arguments
                    if isinstance(arguments, str)
                    else json.dumps(arguments or {}, ensure_ascii=False),
                },
            }
        )
    return calls


def _status(db: Session, session: AgentSession, status: str) -> None:
    session.status = status
    session.updated_at = utcnow()
    db.commit()


def _finish(db: Session, session: AgentSession, status: str) -> dict[str, Any]:
    _status(db, session, status)
    return {"event": "turn_end", "data": {"status": status}}


def _client_queue(
    calls: list[dict[str, Any]], decisions: dict[str, SafetyDecision]
) -> dict[str, Any]:
    queue = []
    for call in calls:
        name = call["function"]["name"]
        try:
            args = json.loads(call["function"]["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {}
        decision = decisions.get(call["id"])
        queue.append(
            {
                "id": call["id"],
                "name": name,
                "arguments": call["function"]["arguments"],
                "args": args,
                "requires_confirm": bool(decision and decision.requires_confirm),
                "risk": decision.risk if decision else "",
                "title": decision.title if decision else "",
            }
        )
    return {"calls": queue}


def client_tool_events(queued: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield {"event": "client_tool_request", "data": queued}
    yield {"event": "turn_end", "data": {"status": "awaiting_client"}}


def take_queued_client(db: Session, session: AgentSession) -> dict[str, Any] | None:
    state = dict(session.skill_state or {})
    queued = state.pop("queued_client", None)
    if not queued:
        return None
    session.skill_state = state
    _status(db, session, "running")
    return queued


def cancel_pending(db: Session, session: AgentSession, reason: str = "用户取消了操作") -> None:
    """取消待确认和待浏览器执行的调用，并补齐工具结果。"""
    state = dict(session.skill_state or {})
    calls = list(state.pop("pending", []) or [])
    queued = state.pop("queued_client", {}) or {}
    calls.extend(queued.get("calls") or [])
    for call in calls:
        _save_tool(
            db,
            session,
            str(call.get("id") or ""),
            str(call.get("name") or ""),
            {"error": reason},
        )
    session.skill_state = state
    session.status = "cancelled"
    session.updated_at = utcnow()
    db.commit()


def apply_tool_results(
    db: Session,
    session: AgentSession,
    results: list[dict[str, Any]],
    approved: bool | None = None,
) -> None:
    del approved
    for item in results or []:
        if not isinstance(item, dict):
            continue
        _save_tool(
            db,
            session,
            str(item.get("tool_call_id") or ""),
            str(item.get("name") or ""),
            item.get("result"),
        )
    state = dict(session.skill_state or {})
    state.pop("queued_client", None)
    session.skill_state = state
    _status(db, session, "running")


async def _stream_model(
    adapter: Any,
    session: AgentSession,
    messages: list[dict[str, Any]],
    native_tools: bool,
) -> AsyncIterator[tuple[str, Any]]:
    model = session.model or ""
    if native_tools and hasattr(adapter, "chat_full"):
        async for event in adapter.chat_full(
            model=model, messages=messages, tools=TOOL_SCHEMAS
        ):
            yield event
        return
    if hasattr(adapter, "chat"):
        text = await adapter.chat(model=model, messages=messages)
        cleaned, calls = parse_text_tool_calls(str(text or ""))
        if cleaned:
            yield ("text", cleaned)
        yield ("done", calls)
        return
    # 最后兜底：只支持 chat_stream 的适配器，拼接后按文本协议解析
    chunks: list[str] = []
    if hasattr(adapter, "chat_stream"):
        async for chunk in adapter.chat_stream(model=model, messages=messages):
            chunks.append(str(chunk))
    cleaned, calls = parse_text_tool_calls("".join(chunks))
    if cleaned:
        yield ("text", cleaned)
    yield ("done", calls)


async def iter_turn(
    db: Session,
    session: AgentSession,
    user: User,
    adapter: Any,
    jobs: Any = None,
    *,
    native_tools: bool = True,
    vision: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """跑一段对话，直到需要用户输入、需要浏览器执行工具或正常结束。"""
    _CANCELS.discard(session.id)
    _status(db, session, "running")
    effective_native = bool(native_tools and hasattr(adapter, "chat_full"))
    messages = _history(db, session, vision)
    system_prompt = build_system_prompt(
        db, session.owner_id, session, native_tools=effective_native
    )
    model_messages = [{"role": "system", "content": system_prompt}, *messages]

    for _step in range(MAX_STEPS):
        if _cancelled(session.id):
            _CANCELS.discard(session.id)
            yield _finish(db, session, "cancelled")
            return
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        raw_calls: list[Any] = []
        try:
            async for kind, payload in _stream_model(
                adapter, session, model_messages, effective_native
            ):
                if kind == "text":
                    text_parts.append(str(payload))
                    yield {"event": "token", "data": {"text": str(payload)}}
                elif kind == "reasoning":
                    reasoning_parts.append(str(payload))
                elif kind == "done":
                    raw_calls = payload or []
        except Exception as exc:  # noqa: BLE001 —— 模型/网络错误要变成对话事件
            logger.warning("导演台模型调用失败: {}", exc)
            yield {"event": "token", "data": {"text": f"\n\n模型调用失败：{exc}"}}
            yield _finish(db, session, "idle")
            return
        reasoning = "".join(reasoning_parts)
        if _cancelled(session.id):
            _CANCELS.discard(session.id)
            _save_assistant(db, session, "".join(text_parts), [], reasoning)
            yield _finish(db, session, "cancelled")
            return

        text = "".join(text_parts)
        calls = _normalize_calls(raw_calls)
        _save_assistant(db, session, text, calls, reasoning)
        if calls:
            assistant: dict[str, Any] = {
                "role": "assistant",
                "content": text,
                "tool_calls": calls,
            }
            if reasoning:
                assistant["reasoning_content"] = reasoning
            model_messages.append(assistant)
        if not calls:
            yield _finish(db, session, "idle")
            return

        server_calls = [c for c in calls if not is_client_tool(c["function"]["name"])]
        client_calls = [c for c in calls if is_client_tool(c["function"]["name"])]
        decisions = {
            call["id"]: decide_tool(session, call["function"]["name"]) for call in calls
        }

        ask = next((c for c in server_calls if c["function"]["name"] == "ask_user"), None)
        if ask is not None:
            result: Any = {}
            async for event in run_server_tool(
                db,
                session,
                user,
                jobs,
                ask["function"]["name"],
                ask["function"]["arguments"],
            ):
                if event["event"] == "tool_result":
                    result = event["data"]
            _save_tool(db, session, ask["id"], ask["function"]["name"], result)
            _reject_calls(
                db,
                session,
                [c for c in calls if c["id"] != ask["id"]],
                "等待用户回答，这次调用已取消；回答后可以重新调用。",
            )
            yield {"event": "ask_user", "data": result}
            yield _finish(db, session, "idle")
            return

        needs_confirm = [
            c for c in server_calls if decisions[c["id"]].requires_confirm
        ]
        if needs_confirm:
            confirm_ids = {c["id"] for c in needs_confirm}
            _reject_calls(
                db,
                session,
                [c for c in calls if c["id"] not in confirm_ids],
                "等待用户确认操作，这次调用已取消；确认后可以重新调用。",
            )
            state = dict(session.skill_state or {})
            state["pending"] = [
                {
                    "id": c["id"],
                    "name": c["function"]["name"],
                    "arguments": c["function"]["arguments"],
                    "risk": decisions[c["id"]].risk,
                    "title": decisions[c["id"]].title,
                }
                for c in needs_confirm
            ]
            session.skill_state = state
            _status(db, session, "awaiting_confirm")
            yield {
                "event": "confirm",
                "data": {"kind": "server", "calls": state["pending"]},
            }
            yield {"event": "turn_end", "data": {"status": "awaiting_confirm"}}
            return

        for call in server_calls:
            name = call["function"]["name"]
            yield {
                "event": "tool_start",
                "data": {
                    "id": call["id"],
                    "name": name,
                    "arguments": call["function"]["arguments"],
                },
            }
            result = {}
            try:
                async for event in run_server_tool(
                    db, session, user, jobs, name, call["function"]["arguments"]
                ):
                    if event["event"] == "tool_result":
                        result = event["data"]
                    else:
                        yield event
            except Exception as exc:  # noqa: BLE001
                result = {"error": str(exc)}
            _save_tool(db, session, call["id"], name, result)
            yield {
                "event": "tool_end",
                "data": {
                    "id": call["id"],
                    "name": name,
                    "ok": not (isinstance(result, dict) and result.get("error")),
                    "result": result,
                },
            }
            model_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

        if client_calls:
            queued = _client_queue(client_calls, decisions)
            state = dict(session.skill_state or {})
            state["queued_client"] = queued
            session.skill_state = state
            _status(db, session, "awaiting_client")
            for event in client_tool_events(queued):
                yield event
            return

    message = "已达到单轮 25 步上限，先停在这里。请检查上面的结果，确认后继续。"
    _save_assistant(db, session, message, [])
    yield {"event": "token", "data": {"text": message}}
    yield _finish(db, session, "idle")


async def run_approved(
    db: Session, session: AgentSession, user: User, jobs: Any
) -> AsyncIterator[dict[str, Any]]:
    """用户同意后执行暂存的生成类工具。"""
    state = dict(session.skill_state or {})
    pending = state.pop("pending", [])
    if not pending:
        return
    state["approved_running"] = pending
    session.skill_state = state
    _status(db, session, "running")
    remaining = {str(call.get("id") or ""): call for call in pending}
    try:
        for call in pending:
            name = str(call.get("name") or "")
            call_id = str(call.get("id") or "")
            yield {
                "event": "tool_start",
                "data": {"id": call_id, "name": name, "arguments": call.get("arguments")},
            }
            result: Any = {}
            try:
                async for event in run_server_tool(
                    db, session, user, jobs, name, call.get("arguments")
                ):
                    if event["event"] == "tool_result":
                        result = event["data"]
                    else:
                        yield event
            except Exception as exc:  # noqa: BLE001
                result = {"error": str(exc)}
            _save_tool(db, session, call_id, name, result)
            remaining.pop(call_id, None)
            yield {
                "event": "tool_end",
                "data": {
                    "id": call_id,
                    "name": name,
                    "ok": not (isinstance(result, dict) and result.get("error")),
                    "result": result,
                },
            }
    finally:
        if remaining:
            for call in remaining.values():
                _save_tool(
                    db,
                    session,
                    str(call.get("id") or ""),
                    str(call.get("name") or ""),
                    {"error": "任务中断，操作已取消"},
                )
        state = dict(session.skill_state or {})
        state.pop("approved_running", None)
        session.skill_state = state
        db.commit()
