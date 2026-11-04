"""导演台：工具调用解析、技能包拒绝、视觉拦截、图片合成、假模型完整循环。"""

from __future__ import annotations

import asyncio
import io
import json
import zipfile
from io import BytesIO
from typing import Any

import httpx
import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import select

from liberastra.agent.context import assemble_user_content
from liberastra.agent.protocol import parse_text_tool_calls
from liberastra.agent.skills import SkillError, validate_skill_files
from liberastra.core.db import SessionLocal
from liberastra.models import Asset, Job, User
from liberastra.providers.llm.tool_stream import iter_openai_chat
from liberastra.services.media_jobs import _concat_images
from liberastra.storage.local import resolve, save_bytes


def test_parse_text_tool_calls():
    text = '先看一下<tool_call>{"name":"canvas_get_graph","arguments":{}}</tool_call>'
    cleaned, calls = parse_text_tool_calls(text)
    assert "tool_call" not in cleaned
    assert calls[0]["name"] == "canvas_get_graph"
    assert json.loads(calls[0]["arguments"]) == {}


def test_parse_qwen_xml_tool_call():
    text = """好的，我来添加。
<tool_call>
<function=canvas_add_node>
<parameter=canvasId>
abc-123
</parameter>
<parameter=kind>
text_input
</parameter>
<parameter=data>
{"text": "测试文本", "varName": "input_text_1"}
</parameter>
<parameter=x>
100
</parameter>
</function>
</tool_call>
"""
    cleaned, calls = parse_text_tool_calls(text)
    assert "tool_call" not in cleaned
    assert "canvas_add_node" not in cleaned
    assert cleaned == "好的，我来添加。"
    assert calls[0]["name"] == "canvas_add_node"
    assert json.loads(calls[0]["arguments"]) == {
        "canvasId": "abc-123",
        "kind": "text_input",
        "data": {"text": "测试文本", "varName": "input_text_1"},
        "x": 100,
    }


def test_parse_strips_think_tags():
    text = (
        "<think>先想一下</think>看一下</think>"
        '<tool_call>{"name":"canvas_get_graph","arguments":{}}</tool_call>'
    )
    cleaned, calls = parse_text_tool_calls(text)
    assert "think" not in cleaned
    assert cleaned == "看一下"
    assert calls[0]["name"] == "canvas_get_graph"


def test_openai_stream_accumulates_tool_calls():
    first = {
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "c1",
                            "function": {"name": "list_assets", "arguments": ""},
                        }
                    ]
                }
            }
        ]
    }
    second = {
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {"index": 0, "function": {"arguments": '{"kind":"image"}'}}
                    ]
                }
            }
        ]
    }
    lines = [f"data: {json.dumps(first)}", f"data: {json.dumps(second)}", "data: [DONE]"]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200, text="\n".join(lines) + "\n")

    async def run() -> list:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http:
            events = [
                item
                async for item in iter_openai_chat(
                    http, "http://llm.test/chat/completions", {}, {"model": "fake"}, timeout=5
                )
            ]
        return events

    events = asyncio.run(run())
    assert events[-1][0] == "done"
    assert events[-1][1][0]["name"] == "list_assets"
    assert json.loads(events[-1][1][0]["arguments"])["kind"] == "image"


def test_openai_stream_emits_reasoning_content():
    chunks = [
        {"choices": [{"delta": {"reasoning_content": "先想"}}]},
        {"choices": [{"delta": {"reasoning_content": "一下"}}]},
        {"choices": [{"delta": {"content": "答案"}}]},
    ]
    lines = [f"data: {json.dumps(chunk)}" for chunk in chunks] + ["data: [DONE]"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="\n".join(lines) + "\n")

    async def run() -> list:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http:
            return [
                item
                async for item in iter_openai_chat(
                    http, "http://llm.test/chat/completions", {}, {"model": "fake"}, timeout=5
                )
            ]

    events = asyncio.run(run())
    assert ("reasoning", "先想一下") in events
    assert ("text", "答案") in events


def test_history_keeps_reasoning_for_tool_calls(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        from liberastra.agent.runtime import _history, _save_assistant

        _user, session = _agent_session(db)
        calls = [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "canvas_get_graph", "arguments": "{}"},
            }
        ]
        _save_assistant(db, session, "", calls, reasoning="内部推理")
        db.refresh(session)
        messages = _history(db, session, vision=False)
        assistant = next(item for item in messages if item.get("tool_calls"))
        assert assistant["reasoning_content"] == "内部推理"
    finally:
        db.close()


def test_anthropic_tool_message_conversion():
    from liberastra.providers.vendors.cloud.anthropic import (
        _anthropic_messages,
        _anthropic_tools,
    )

    system, dialog = _anthropic_messages(
        [
            {"role": "system", "content": "系统提示"},
            {
                "role": "assistant",
                "content": "先看图",
                "tool_calls": [
                    {
                        "id": "c1",
                        "function": {
                            "name": "load_skill",
                            "arguments": '{"name":"director"}',
                        },
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "c1", "content": '{"ok":true}'},
        ]
    )
    assert system == ["系统提示"]
    assert dialog[0]["content"][1] == {
        "type": "tool_use",
        "id": "c1",
        "name": "load_skill",
        "input": {"name": "director"},
    }
    assert dialog[1]["content"][0]["type"] == "tool_result"
    tools = _anthropic_tools(
        [
            {
                "type": "function",
                "function": {
                    "name": "canvas_get_graph",
                    "description": "读取画布",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
    )
    assert tools[0]["input_schema"]["type"] == "object"


def _sse_events(text: str) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        name = ""
        data: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data.append(line.split(":", 1)[1].lstrip())
        if name:
            events.append((name, "\n".join(data)))
    return events


def test_two_client_tool_batches_keep_session_usable(client, auth_header, monkeypatch):
    provider = client.post(
        "/api/v1/providers",
        headers=auth_header,
        json={
            "name": "agent-two-batch",
            "type": "openai_compatible",
            "base_url": "http://127.0.0.1:9/v1",
        },
    )
    assert provider.status_code == 201
    provider_id = provider.json()["id"]
    catalog = client.put(
        f"/api/v1/providers/{provider_id}/catalog",
        headers=auth_header,
        json={
            "models": [
                {
                    "id": "fake-tool",
                    "label": "Fake Tool",
                    "category": "llm",
                    "sub_capabilities": ["chat", "tools"],
                    "enabled": True,
                    "custom": True,
                }
            ]
        },
    )
    assert catalog.status_code == 200
    session = client.post(
        "/api/v1/agent/sessions",
        headers=auth_header,
        json={"provider_id": provider_id, "model": "fake-tool"},
    )
    assert session.status_code == 201
    session_id = session.json()["id"]

    class Fake:
        def __init__(self) -> None:
            self.calls = 0

        async def chat_full(self, **_kwargs: object):
            self.calls += 1
            if self.calls == 1:
                yield (
                    "done",
                    [
                        {
                            "id": "a1",
                            "name": "canvas_add_node",
                            "arguments": '{"kind":"input","media_kind":"text"}',
                        }
                    ],
                )
            elif self.calls == 2:
                yield (
                    "done",
                    [{"id": "a2", "name": "canvas_get_graph", "arguments": "{}"}],
                )
            else:
                yield ("text", "完成")
                yield ("done", [])

    fake = Fake()
    monkeypatch.setattr(
        "liberastra.api.routes.agent.build_adapter", lambda _provider: fake
    )

    first = client.post(
        f"/api/v1/agent/sessions/{session_id}/turns",
        headers=auth_header,
        json={"text": "加节点", "attachments": [], "refs": []},
    )
    assert first.status_code == 200
    first_events = dict(_sse_events(first.text))
    assert "client_tool_request" in first_events
    assert '"name": "canvas_add_node"' in first_events["client_tool_request"]

    second = client.post(
        f"/api/v1/agent/sessions/{session_id}/tool-results",
        headers=auth_header,
        json={
            "results": [
                {
                    "tool_call_id": "a1",
                    "name": "canvas_add_node",
                    "result": {"node_id": "n1"},
                }
            ]
        },
    )
    assert second.status_code == 200
    second_events = dict(_sse_events(second.text))
    assert "client_tool_request" in second_events
    assert '"name": "canvas_get_graph"' in second_events["client_tool_request"]

    third = client.post(
        f"/api/v1/agent/sessions/{session_id}/tool-results",
        headers=auth_header,
        json={
            "results": [
                {
                    "tool_call_id": "a2",
                    "name": "canvas_get_graph",
                    "result": {"graph": {}},
                }
            ]
        },
    )
    assert third.status_code == 200
    assert "完成" in third.text
    assert fake.calls == 3


def test_skill_upload_allows_standard_resources():
    from liberastra.agent.skills import list_skill_files, read_skill, save_skill_files

    files = {
        "SKILL.md": (
            b"---\n"
            b"name: demo-skill\n"
            b"description: Demo skill for tests.\n"
            b"license: MIT\n"
            b"compatibility: Requires Python 3.12+\n"
            b"metadata:\n"
            b"  author: test\n"
            b"  version: \"1.0\"\n"
            b"allowed-tools: canvas_get_graph run_skill_script\n"
            b"---\n\n# demo\n"
        ),
        "scripts/run.py": b"print('ok')\n",
        "references/guide.md": b"# guide\n",
        "assets/template.json": b"{}\n",
        "assets/data.bin": b"\x00\x01\x02",
        "showcase.html": b"<!doctype html><html><body>showcase</body></html>\n",
    }
    name = save_skill_files(files)
    assert name == "demo-skill"
    meta, _body = read_skill(name)
    assert meta["license"] == "MIT"
    assert meta["compatibility"] == "Requires Python 3.12+"
    assert meta["metadata"] == {"author": "test", "version": "1.0"}
    assert meta["allowed_tools"] == ["canvas_get_graph", "run_skill_script"]
    paths = {item["path"] for item in list_skill_files(name)}
    assert {"SKILL.md", "scripts/run.py", "assets/data.bin"} <= paths


def test_skill_upload_rejects_path_traversal():
    files = {
        "SKILL.md": b"---\nname: demo-skill\ndescription: example\n---\n\n# demo\n",
        "../evil.py": b"print(1)\n",
    }
    with pytest.raises(SkillError):
        validate_skill_files(files)


def test_skill_standard_name_rules():
    for name in ("Bad-Name", "-bad", "bad-", "bad--name"):
        files = {
            "SKILL.md": (
                f"---\nname: {name}\ndescription: example\n---\n\n# demo\n"
            ).encode()
        }
        with pytest.raises(SkillError):
            validate_skill_files(files)


def test_agent_client_tools_include_function_application():
    from liberastra.agent.safety import TOOL_RISKS
    from liberastra.agent.tools import CLIENT_TOOL_NAMES, TOOL_SCHEMAS

    assert {"canvas_apply_menu", "canvas_apply_pack", "canvas_get_node_schema"} <= CLIENT_TOOL_NAMES
    names = {item["function"]["name"] for item in TOOL_SCHEMAS}
    assert {"canvas_apply_menu", "canvas_apply_pack", "canvas_get_node_schema"} <= names
    assert TOOL_RISKS["canvas_apply_menu"] == "canvas_write"
    assert TOOL_RISKS["canvas_apply_pack"] == "canvas_write"
    assert TOOL_RISKS["canvas_get_node_schema"] == "read"


def _read_tool(name: str, arguments: dict[str, Any]) -> Any:
    from types import SimpleNamespace

    from liberastra.agent.tools import run_server_tool

    async def run():
        db = SessionLocal()
        try:
            user = db.scalar(select(User).where(User.username == "admin"))
            assert user is not None
            events = [
                event
                async for event in run_server_tool(
                    db,
                    SimpleNamespace(skill_state={}),
                    user,
                    None,
                    name,
                    arguments,
                )
            ]
            return events[-1]["data"]
        finally:
            db.close()

    return asyncio.run(run())


def test_agent_read_tools_expose_menu_targets_and_resource_specs(client, auth_header):
    assert client is not None and auth_header
    menu = _read_tool("list_canvas_menu", {})
    by_id = {item["id"]: item for item in menu["items"]}
    first = by_id["preset_i2v_first"]
    assert first["enabled"] is True
    assert first["media_slots"][0]["type"] == "image"
    assert first["available_targets"]
    assert first["default_target_resolved"]["target_type"] == "workflow"
    ref = by_id["preset_v2v_ref"]
    assert ref["default_target_resolved"]["target_id"] == "minimax_h3_i2v_ref"
    assert ref["default_target_resolved"]["media_slots"][0]["key"] == "image"
    assert ref["media_slots"][0]["required"] is True
    assert ref["media_slots"][0]["multiple"] is False
    assert "length" in ref["default_target_resolved"]["input_keys"]

    workflow = _read_tool("list_workflows", {"name": "minimax_h3_i2v_ref"})["workflow"]
    assert workflow["fps"] == 24
    assert workflow["inputs"]["length"]["max"] == 362
    assert workflow["inputs"]["length"]["align_base"] == 17

    specs = _read_tool("list_execution_specs", {"sub_capability": "v2v_ref"})["specs"]
    assert specs
    assert any(spec["media_slots"][0]["key"] == "image" for spec in specs)


def test_agent_read_tools_assets_voices_music(client, auth_header):
    assert client is not None and auth_header
    from liberastra.models import Voice
    from liberastra.storage.local import create_asset

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.username == "admin"))
        assert user is not None
        buffer = BytesIO()
        Image.new("RGB", (48, 32), (12, 34, 56)).save(buffer, format="PNG")
        save_bytes(buffer.getvalue(), "uploads/agent-tool-test.png")
        asset = create_asset(
            db,
            kind="image",
            rel_path="uploads/agent-tool-test.png",
            owner_id=user.id,
            meta={"source_name": "tool-test.png"},
        )
        voice = Voice(name="测试音色", owner_id=user.id, tags=["test"], is_default=True)
        db.add(voice)
        db.commit()
        voice_id = voice.id
        asset_id = asset.id
    finally:
        db.close()

    got = _read_tool("get_asset", {"asset_id": asset_id, "probe_media": True})["asset"]
    assert got["name"] == "tool-test.png"
    assert got["media"]["width"] == 48
    assert got["media"]["height"] == 32

    voices = _read_tool("list_voices", {})["voices"]
    assert any(item["id"] == voice_id and item["has_ref_audio"] is False for item in voices)

    save_bytes(b"ID3", "bgm/agent-tool-test.mp3")
    music = _read_tool("list_music", {})["music"]
    assert any(item["path"] == "bgm/agent-tool-test.mp3" for item in music)


def test_safety_router_defaults_and_session_auto():
    from types import SimpleNamespace

    from liberastra.agent.safety import decide_tool, remember_auto

    session = SimpleNamespace(skill_state={})
    assert decide_tool(session, "canvas_get_graph").action == "allow"
    assert decide_tool(session, "canvas_add_node").action == "allow"
    delete = decide_tool(session, "canvas_delete_nodes")
    assert delete.action == "confirm"
    assert delete.risk == "destructive"
    generate = decide_tool(session, "canvas_run_nodes")
    assert generate.action == "confirm"
    assert generate.risk == "generate"
    script = decide_tool(session, "run_skill_script")
    assert script.action == "confirm"
    assert script.risk == "script"

    remember_auto(session, ["canvas_delete_nodes"])
    assert decide_tool(session, "canvas_delete_nodes").action == "allow"
    assert decide_tool(session, "generate_image").action == "confirm"


def test_save_skill_file_writes_resources_only():
    from liberastra.agent.skills import (
        SkillError,
        read_skill_file,
        save_skill_file,
        save_skill_text,
    )

    name = save_skill_text("resource-skill", "resource test", "# demo")
    written = save_skill_file(name, "references/guide.md", "# guide\n")
    assert written == "references/guide.md"
    assert read_skill_file(name, "references/guide.md") == "# guide\n"
    with pytest.raises(SkillError):
        save_skill_file(name, "../outside.md", "x")
    with pytest.raises(SkillError):
        save_skill_file(name, "SKILL.md", "---\n---\n")


def test_run_skill_script_with_args():
    from liberastra.agent.script_runner import run_skill_script
    from liberastra.agent.skills import save_skill_files

    name = save_skill_files(
        {
            "SKILL.md": b"---\nname: demo-runner\ndescription: runner\n---\n\n# demo\n",
            "scripts/echo.py": (
                b"import sys\nprint('hello', sys.argv[1])\n"
            ),
        }
    )
    result = asyncio.run(run_skill_script(name, "scripts/echo.py", ["world"], timeout=20))
    assert result["exit_code"] == 0
    assert "hello world" in result["stdout"]

    with pytest.raises(SkillError):
        asyncio.run(run_skill_script(name, "../SKILL.md", []))


def _png(color: str, size: tuple[int, int]) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_vision_rejected_without_capability(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        raw = _png("red", (8, 8))
        rel = "uploads/vision-check.png"
        save_bytes(raw, rel)
        asset = Asset(
            kind="image",
            path=rel,
            mime="image/png",
            size=len(raw),
            owner_id=user.id,
            hidden=True,
            meta={},
        )
        db.add(asset)
        db.commit()
        with pytest.raises(HTTPException) as caught:
            assemble_user_content(
                db,
                user.id,
                {"text": "看图", "attachments": [{"asset_id": asset.id, "kind": "image"}]},
                vision=False,
            )
        assert caught.value.status_code == 400
    finally:
        db.close()


def test_ref_media_is_not_duplicated(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        raw = _png("green", (8, 8))
        rel = "uploads/ref-once.png"
        save_bytes(raw, rel)
        asset = Asset(
            kind="image",
            path=rel,
            mime="image/png",
            size=len(raw),
            owner_id=user.id,
            hidden=True,
            meta={},
        )
        db.add(asset)
        db.commit()
        parts = assemble_user_content(
            db,
            user.id,
            {
                "text": "看这张",
                "refs": [
                    {
                        "node_id": "n1",
                        "var_name": "output_image_1",
                        "assets": [{"asset_id": asset.id, "kind": "image"}],
                        "asset_ids": [asset.id],
                    }
                ],
            },
            vision=True,
        )
        assert sum(1 for part in parts if part.get("type") == "image_url") == 1
    finally:
        db.close()


def test_image_ref_does_not_require_vision(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        raw = _png("blue", (8, 8))
        rel = "uploads/ref-no-vision.png"
        save_bytes(raw, rel)
        asset = Asset(
            kind="image",
            path=rel,
            mime="image/png",
            size=len(raw),
            owner_id=user.id,
            hidden=True,
            meta={},
        )
        db.add(asset)
        db.commit()
        parts = assemble_user_content(
            db,
            user.id,
            {
                "text": "断开这个节点连线",
                "refs": [
                    {
                        "node_id": "n2",
                        "var_name": "input_image_1",
                        "title": "图片输入",
                        "config": {"mediaKind": "image"},
                        "assets": [{"asset_id": asset.id, "kind": "image"}],
                        "asset_ids": [asset.id],
                    }
                ],
            },
            vision=False,
        )
        assert not [part for part in parts if part.get("type") == "image_url"]
        assert any("未附带" in str(part.get("text", "")) for part in parts)
    finally:
        db.close()


def _stored_image(db, user, name: str, color: str = "red") -> Asset:
    raw = _png(color, (8, 8))
    rel = f"uploads/{name}"
    save_bytes(raw, rel)
    asset = Asset(
        kind="image",
        path=rel,
        mime="image/png",
        size=len(raw),
        owner_id=user.id,
        hidden=True,
        meta={},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def test_node_only_attachment_does_not_require_vision(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        asset = _stored_image(db, user, "node-only.png")
        parts = assemble_user_content(
            db,
            user.id,
            {
                "text": "把附件放到图片输入节点",
                "attachments": [
                    {
                        "asset_id": asset.id,
                        "kind": "image",
                        "name": "node-only.png",
                        "send_to_model": False,
                    }
                ],
            },
            vision=False,
        )
        assert not [part for part in parts if part.get("type") == "image_url"]
        text = "\n".join(
            str(part.get("text", "")) for part in parts if part.get("type") == "text"
        )
        assert f"asset_id={asset.id}" in text
        assert "仅用于画布节点" in text
    finally:
        db.close()


def test_node_only_attachment_stays_text_with_vision(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        asset = _stored_image(db, user, "node-only-vision.png")
        parts = assemble_user_content(
            db,
            user.id,
            {
                "text": "把附件放到图片输入节点",
                "attachments": [
                    {
                        "asset_id": asset.id,
                        "kind": "image",
                        "name": "node-only-vision.png",
                        "send_to_model": False,
                    }
                ],
            },
            vision=True,
        )
        assert not [part for part in parts if part.get("type") == "image_url"]
        text = "\n".join(
            str(part.get("text", "")) for part in parts if part.get("type") == "text"
        )
        assert f"asset_id={asset.id}" in text
        assert "仅用于画布节点" in text
    finally:
        db.close()


def test_model_attachment_keeps_asset_id_text(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        asset = _stored_image(db, user, "model-attachment.png")
        parts = assemble_user_content(
            db,
            user.id,
            {
                "text": "看图，同时把这个资源放到节点",
                "attachments": [
                    {
                        "asset_id": asset.id,
                        "kind": "image",
                        "name": "model-attachment.png",
                        "send_to_model": True,
                    }
                ],
            },
            vision=True,
        )
        assert len([part for part in parts if part.get("type") == "image_url"]) == 1
        text = "\n".join(
            str(part.get("text", "")) for part in parts if part.get("type") == "text"
        )
        assert f"asset_id={asset.id}" in text
        assert "也可用于画布节点" in text
    finally:
        db.close()


class _Ctx:
    def report(self, *args: Any, **kwargs: Any) -> None:
        return None

    def cancelled(self) -> bool:
        return False


def test_image_concat_horizontal_default_gap(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        ids = []
        for color, name in (("red", "concat-a.png"), ("blue", "concat-b.png")):
            raw = _png(color, (20, 10))
            rel = f"uploads/{name}"
            save_bytes(raw, rel)
            asset = Asset(
                kind="image",
                path=rel,
                mime="image/png",
                size=len(raw),
                owner_id=user.id,
                hidden=True,
                meta={},
            )
            db.add(asset)
            db.commit()
            ids.append(asset.id)
        job = Job(
            kind="media.concat",
            status="running",
            params={
                "kind": "image",
                "asset_ids": ids,
                "layout": "horizontal",
                "gap_color": "#FFFFFF",
            },
            owner_id=user.id,
            outputs=[],
            steps=[],
        )
        db.add(job)
        db.commit()
        outputs = _concat_images(db, job, _Ctx())
        saved = db.get(Asset, outputs[0]["asset_id"])
        assert saved is not None
        with Image.open(resolve(saved.path)) as image:
            assert image.width == 44
            assert image.height == 10
    finally:
        db.close()


def test_image_concat_grid_is_compact_for_mixed_aspects(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        ids = []
        specs = (
            ("red", (100, 50)),
            ("blue", (50, 100)),
            ("green", (50, 100)),
            ("yellow", (100, 50)),
        )
        for index, (color, size) in enumerate(specs):
            raw = _png(color, size)
            rel = f"uploads/concat-grid-{index}.png"
            save_bytes(raw, rel)
            asset = Asset(
                kind="image",
                path=rel,
                mime="image/png",
                size=len(raw),
                owner_id=user.id,
                hidden=True,
                meta={},
            )
            db.add(asset)
            db.commit()
            ids.append(asset.id)
        job = Job(
            kind="media.concat",
            status="running",
            params={
                "kind": "image",
                "asset_ids": ids,
                "layout": "grid",
                "columns": 2,
                "gap": 4,
                "gap_color": "#000000",
            },
            owner_id=user.id,
            outputs=[],
            steps=[],
        )
        db.add(job)
        db.commit()
        outputs = _concat_images(db, job, _Ctx())
        saved = db.get(Asset, outputs[0]["asset_id"])
        assert saved is not None
        with Image.open(resolve(saved.path)).convert("RGB") as image:
            assert image.size == (129, 104)
            assert image.getpixel((100, 0)) == (0, 0, 0)
            assert image.getpixel((25, 54)) == (0, 0, 0)
    finally:
        db.close()


def test_image_concat_grid_row_major_for_first_and_last_frames(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        colors = ["red", "lime", "blue", "yellow", "magenta", "cyan"]
        ids = []
        for index, color in enumerate(colors):
            raw = _png(color, (20, 20))
            rel = f"uploads/storyboard-grid-{index}.png"
            save_bytes(raw, rel)
            asset = Asset(
                kind="image",
                path=rel,
                mime="image/png",
                size=len(raw),
                owner_id=user.id,
                hidden=True,
                meta={},
            )
            db.add(asset)
            db.commit()
            ids.append(asset.id)
        job = Job(
            kind="media.concat",
            status="running",
            params={
                "kind": "image",
                "asset_ids": ids,
                "layout": "grid",
                "columns": 3,
                "gap": 4,
                "gap_color": "#000000",
            },
            owner_id=user.id,
            outputs=[],
            steps=[],
        )
        db.add(job)
        db.commit()
        outputs = _concat_images(db, job, _Ctx())
        saved = db.get(Asset, outputs[0]["asset_id"])
        assert saved is not None
        with Image.open(resolve(saved.path)).convert("RGB") as image:
            assert image.size == (68, 44)
            # 第一行：分镜 1/2/3 的首帧；第二行：对应尾帧。
            assert image.getpixel((10, 10)) == (255, 0, 0)
            assert image.getpixel((34, 10)) == (0, 255, 0)
            assert image.getpixel((58, 10)) == (0, 0, 255)
            assert image.getpixel((10, 34)) == (255, 255, 0)
            assert image.getpixel((34, 34)) == (255, 0, 255)
            assert image.getpixel((58, 34)) == (0, 255, 255)
    finally:
        db.close()


def test_image_concat_grid_single_row_for_first_frame_only(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user = db.scalars(select(User)).first()
        assert user is not None
        ids = []
        for index, color in enumerate(("red", "lime", "blue")):
            raw = _png(color, (20, 20))
            rel = f"uploads/storyboard-row-{index}.png"
            save_bytes(raw, rel)
            asset = Asset(
                kind="image",
                path=rel,
                mime="image/png",
                size=len(raw),
                owner_id=user.id,
                hidden=True,
                meta={},
            )
            db.add(asset)
            db.commit()
            ids.append(asset.id)
        job = Job(
            kind="media.concat",
            status="running",
            params={
                "kind": "image",
                "asset_ids": ids,
                "layout": "grid",
                "columns": 3,
                "gap": 4,
                "gap_color": "#000000",
            },
            owner_id=user.id,
            outputs=[],
            steps=[],
        )
        db.add(job)
        db.commit()
        outputs = _concat_images(db, job, _Ctx())
        saved = db.get(Asset, outputs[0]["asset_id"])
        assert saved is not None
        with Image.open(resolve(saved.path)).convert("RGB") as image:
            assert image.size == (68, 20)
            assert image.getpixel((10, 10)) == (255, 0, 0)
            assert image.getpixel((34, 10)) == (0, 255, 0)
            assert image.getpixel((58, 10)) == (0, 0, 255)
    finally:
        db.close()


def test_agent_session_routes_and_builtin_skills(client, auth_header):
    provider = client.post(
        "/api/v1/providers",
        headers=auth_header,
        json={
            "name": "agent-route-test",
            "type": "openai_compatible",
            "base_url": "http://127.0.0.1:9/v1",
        },
    )
    assert provider.status_code == 201
    provider_id = provider.json()["id"]
    created = client.post(
        "/api/v1/agent/sessions",
        headers=auth_header,
        json={
            "canvas_id": None,
            "title": "路由测试",
            "provider_id": provider_id,
            "model": "fake-model",
        },
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    assert created.json()["status"] == "idle"

    listing = client.get("/api/v1/agent/sessions", headers=auth_header)
    assert listing.status_code == 200
    assert any(item["id"] == session_id for item in listing.json())

    renamed = client.patch(
        f"/api/v1/agent/sessions/{session_id}",
        headers=auth_header,
        json={"title": "改名后"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "改名后"

    messages = client.get(
        f"/api/v1/agent/sessions/{session_id}/messages", headers=auth_header
    )
    assert messages.status_code == 200
    assert messages.json() == []

    skills = client.get("/api/v1/agent/skills", headers=auth_header)
    assert skills.status_code == 200
    names = {item["name"] for item in skills.json()}
    assert {"director", "canvas-auto", "skill-creator", "liberastra", "project-info"} <= names
    assert all(item["enabled"] for item in skills.json())

    detail = client.get("/api/v1/agent/skills/director", headers=auth_header)
    assert detail.status_code == 200
    assert "导演技能" in detail.json()["body"]

    info = client.get("/api/v1/agent/skills/project-info", headers=auth_header)
    assert info.status_code == 200
    assert "只读技能" in info.json()["body"]
    paths = {item["path"] for item in info.json()["files"]}
    expected = {
        "references/resources.md",
        "references/menu-and-targets.md",
        "references/node-parameters.md",
    }
    assert expected <= paths

    removed = client.delete(
        f"/api/v1/agent/sessions/{session_id}", headers=auth_header
    )
    assert removed.status_code == 204


def test_director_skill_confirms_video_mode_before_creating_nodes(client, auth_header):
    detail = client.get("/api/v1/agent/skills/director", headers=auth_header)
    assert detail.status_code == 200
    body = detail.json()["body"]
    assert "选择创作路线" in body
    assert "分镜视频" in body
    assert "一段视频" in body
    assert "参考图生成视频（长）" in body
    assert "用户确认前不要创建任何 `output_video_*` 节点" in body
    assert "subject_definitions" in body
    assert "clips_json" in body
    assert "拼接工具节点" in body
    assert "姿势换姿" in body
    assert "视频增强" in body


def _run_turn_with_calls(db, session, user, calls):
    class Fake:
        async def chat_full(self, **_kwargs):
            yield ("done", calls)

    async def run():
        from liberastra.agent.runtime import iter_turn

        events = [
            item
            async for item in iter_turn(
                db, session, user, Fake(), None, native_tools=True, vision=False
            )
        ]
        return events

    return asyncio.run(run())


def _agent_session(db):
    from liberastra.models import AgentSession

    user = db.scalars(select(User)).first()
    assert user is not None
    session = AgentSession(
        owner_id=user.id,
        title="工具测试",
        model="fake",
        active_skill="",
        skill_state={},
        status="idle",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return user, session


def test_client_tool_is_queued_for_browser(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user, session = _agent_session(db)
        events = _run_turn_with_calls(
            db,
            session,
            user,
            [
                {
                    "id": "c1",
                    "name": "canvas_get_graph",
                    "arguments": "{}",
                }
            ],
        )
        names = [item["event"] for item in events]
        assert "client_tool_request" in names
        assert names[-1] == "turn_end"
        assert events[-1]["data"]["status"] == "awaiting_client"
        db.refresh(session)
        queued = session.skill_state["queued_client"]["calls"]
        assert queued[0]["name"] == "canvas_get_graph"
        assert queued[0]["requires_confirm"] is False
    finally:
        db.close()


def test_cancel_pending_closes_tool_history(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user, session = _agent_session(db)
        _run_turn_with_calls(
            db,
            session,
            user,
            [{"id": "c9", "name": "canvas_get_graph", "arguments": "{}"}],
        )
        from liberastra.agent.runtime import cancel_pending

        cancel_pending(db, session)
        db.refresh(session)
        assert session.status == "cancelled"
        assert "queued_client" not in (session.skill_state or {})
        assistant = next(
            message for message in session.messages if message.role == "assistant"
        )
        call_ids = {call["id"] for call in assistant.content["tool_calls"]}
        tool_ids = {
            message.content["tool_call_id"]
            for message in session.messages
            if message.role == "tool"
        }
        assert call_ids == tool_ids
    finally:
        db.close()


def test_delete_nodes_requires_user_confirmation(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user, session = _agent_session(db)
        events = _run_turn_with_calls(
            db,
            session,
            user,
            [
                {
                    "id": "c2",
                    "name": "canvas_delete_nodes",
                    "arguments": '{"node_ids":["n1"]}',
                }
            ],
        )
        db.refresh(session)
        queued = session.skill_state["queued_client"]["calls"]
        assert queued[0]["requires_confirm"] is True
        assert [item["event"] for item in events][-1] == "turn_end"
    finally:
        db.close()


def test_generation_tool_pauses_for_confirmation(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user, session = _agent_session(db)
        events = _run_turn_with_calls(
            db,
            session,
            user,
            [
                {
                    "id": "c3",
                    "name": "generate_image",
                    "arguments": '{"prompt":"一只猫"}',
                },
                {
                    "id": "c3b",
                    "name": "canvas_get_graph",
                    "arguments": "{}",
                },
            ],
        )
        names = [item["event"] for item in events]
        assert names[0] == "confirm"
        assert names[-1] == "turn_end"
        assert events[-1]["data"]["status"] == "awaiting_confirm"
        db.refresh(session)
        assert session.skill_state["pending"][0]["name"] == "generate_image"
        tool_ids = {
            message.content["tool_call_id"]
            for message in session.messages
            if message.role == "tool"
        }
        assert "c3b" in tool_ids
    finally:
        db.close()


def test_ask_user_keeps_tool_history_complete(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user, session = _agent_session(db)
        events = _run_turn_with_calls(
            db,
            session,
            user,
            [
                {
                    "id": "ask-1",
                    "name": "ask_user",
                    "arguments": '{"question":"继续吗？","options":["继续","停止"]}',
                },
                {
                    "id": "graph-1",
                    "name": "canvas_get_graph",
                    "arguments": "{}",
                },
            ],
        )
        assert events[-1]["event"] == "turn_end"
        assert events[-1]["data"]["status"] == "idle"
        db.refresh(session)
        assistant = next(
            message for message in session.messages if message.role == "assistant"
        )
        call_ids = {call["id"] for call in assistant.content["tool_calls"]}
        tool_ids = {
            message.content["tool_call_id"]
            for message in session.messages
            if message.role == "tool"
        }
        assert call_ids == tool_ids
    finally:
        db.close()


def test_approved_generation_runs_then_continues(auth_header):
    _ = auth_header
    db = SessionLocal()
    try:
        user, session = _agent_session(db)
        _run_turn_with_calls(
            db,
            session,
            user,
            [
                {
                    "id": "c4",
                    "name": "generate_image",
                    "arguments": '{"prompt":"一只猫"}',
                }
            ],
        )
        db.refresh(session)
        assert session.status == "awaiting_confirm"

        class Fake:
            async def chat_full(self, **_kwargs):
                yield ("text", "收到，下面继续。")
                yield ("done", [])

        async def run():
            from liberastra.agent.runtime import iter_turn, run_approved

            approved = [
                item async for item in run_approved(db, session, user, None)
            ]
            follow = [
                item
                async for item in iter_turn(
                    db, session, user, Fake(), None, native_tools=True, vision=False
                )
            ]
            return approved, follow

        approved, follow = asyncio.run(run())
        assert any(item["event"] == "tool_end" for item in approved)
        assert follow[-1]["event"] == "turn_end"
        assert follow[-1]["data"]["status"] == "idle"
        db.refresh(session)
        assert "pending" not in (session.skill_state or {})
        assert session.status == "idle"
    finally:
        db.close()


def _skill_zip(name: str, extra: dict[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "SKILL.md",
            f"---\nname: {name}\ndescription: route test\n---\n\n# {name}\n",
        )
        for path, content in (extra or {}).items():
            archive.writestr(path, content)
    return buffer.getvalue()


def test_skill_upload_route_accepts_standard_packages_and_rejects_bad_names(
    client, auth_header
):
    uploaded = client.post(
        "/api/v1/agent/skills",
        headers=auth_header,
        files={"file": ("skill.zip", _skill_zip("route-skill"), "application/zip")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["name"] == "route-skill"
    listed = client.get("/api/v1/agent/skills", headers=auth_header)
    assert any(item["name"] == "route-skill" for item in listed.json())
    removed = client.delete("/api/v1/agent/skills/route-skill", headers=auth_header)
    assert removed.status_code == 204

    scripted = client.post(
        "/api/v1/agent/skills",
        headers=auth_header,
        files={
            "file": (
                "scripted.zip",
                _skill_zip("scripted-skill", {"scripts/run.py": b"print(1)"}),
                "application/zip",
            )
        },
    )
    assert scripted.status_code == 201
    detail = client.get("/api/v1/agent/skills/scripted-skill", headers=auth_header)
    assert detail.status_code == 200
    assert "scripts/run.py" in {item["path"] for item in detail.json()["files"]}
    client.delete("/api/v1/agent/skills/scripted-skill", headers=auth_header)

    rejected = client.post(
        "/api/v1/agent/skills",
        headers=auth_header,
        files={"file": ("bad.zip", _skill_zip("Bad--Name"), "application/zip")},
    )
    assert rejected.status_code == 400


def test_fake_model_runs_one_tool_then_stops(auth_header):
    _ = auth_header
    db = SessionLocal()

    class Fake:
        def __init__(self) -> None:
            self.calls = 0

        async def chat_full(self, **_kwargs: object):
            self.calls += 1
            if self.calls == 1:
                yield (
                    "done",
                    [
                        {
                            "id": "1",
                            "name": "load_skill",
                            "arguments": '{"name":"director"}',
                        }
                    ],
                )
                return
            yield ("text", "完成")
            yield ("done", [])

    async def run() -> list[str]:
        from liberastra.agent.runtime import iter_turn
        from liberastra.models import AgentSession

        user = db.scalars(select(User)).first()
        assert user is not None
        session = AgentSession(
            owner_id=user.id,
            title="测试",
            model="fake",
            active_skill="",
            skill_state={},
            status="idle",
        )
        db.add(session)
        db.commit()
        events = [
            item["event"]
            async for item in iter_turn(
                db, session, user, Fake(), None, native_tools=True, vision=False
            )
        ]
        return events

    try:
        events = asyncio.run(run())
        assert "tool_end" in events
        assert events[-1] == "turn_end"
    finally:
        db.close()


def test_turn_passes_reasoning_back_with_tool_calls(auth_header):
    _ = auth_header
    db = SessionLocal()

    class Fake:
        def __init__(self) -> None:
            self.seen: list[list[dict[str, Any]]] = []

        async def chat_full(self, **kwargs: object):
            self.seen.append(kwargs["messages"])  # type: ignore[arg-type]
            if len(self.seen) == 1:
                yield ("reasoning", "先想一下")
                yield (
                    "done",
                    [
                        {
                            "id": "1",
                            "name": "load_skill",
                            "arguments": '{"name":"director"}',
                        }
                    ],
                )
                return
            yield ("text", "完成")
            yield ("done", [])

    async def run() -> None:
        from liberastra.agent.runtime import iter_turn

        user, session = _agent_session(db)
        adapter = Fake()
        _ = [
            item
            async for item in iter_turn(
                db, session, user, adapter, None, native_tools=True, vision=False
            )
        ]
        assert len(adapter.seen) >= 2
        assistant = next(
            item
            for item in adapter.seen[1]
            if item.get("role") == "assistant" and item.get("tool_calls")
        )
        assert assistant["reasoning_content"] == "先想一下"

    try:
        asyncio.run(run())
    finally:
        db.close()
