"""分层系统提示：身份、行为准则、工具说明、技能目录和当前状态。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from liberastra.agent.protocol import TOOL_PROTOCOL_PROMPT
from liberastra.agent.skills import list_skill_summaries, read_skill
from liberastra.core.config import get_settings

WORKSPACE_FILES = ("SOUL.md", "AGENTS.md", "TOOLS.md")


def _builtin_dir() -> Path:
    return Path(__file__).resolve().parent / "workspace"


def _user_dir() -> Path:
    return get_settings().data_dir / "agent" / "workspace"


def _section(filename: str) -> str:
    builtin = _builtin_dir() / filename
    text = builtin.read_text(encoding="utf-8").strip() if builtin.is_file() else ""
    user = _user_dir() / filename
    if user.is_file():
        supplement = user.read_text(encoding="utf-8").strip()
        if supplement:
            text = f"{text}\n\n---\n\n{supplement}".strip()
    return text


def _state_view(state: dict[str, Any]) -> dict[str, Any]:
    skipped = {"pending", "queued_client"}
    return {key: value for key, value in state.items() if key not in skipped}


def build_system_prompt(
    db: Session,
    owner_id: int,
    session: Any,
    *,
    native_tools: bool,
) -> str:
    parts = []
    for name in WORKSPACE_FILES:
        section = _section(name)
        if section:
            parts.append(section)
    skills = [item for item in list_skill_summaries(db, owner_id) if item.get("enabled")]
    lines = [f"- {item['name']}：{item['description']}" for item in skills]
    parts.append("# 可用技能\n" + ("\n".join(lines) if lines else "当前没有启用的技能。"))
    if session.active_skill:
        try:
            meta, body = read_skill(session.active_skill)
            parts.append(
                f"# 当前技能：{meta['name']}\n{meta.get('description', '')}\n\n{body}"
            )
        except Exception:  # noqa: BLE001 —— 技能被删时不让整轮失败
            parts.append(f"# 当前技能\n{session.active_skill}（技能文件缺失）")
    state = _state_view(dict(session.skill_state or {}))
    if state:
        parts.append(
            "# 当前会话状态\n"
            + json.dumps(state, ensure_ascii=False, indent=2)[:6000]
            + "\n\n继续之前先核对这里记录的进度，不要重复已经完成的步骤。"
        )
    if not native_tools:
        parts.append(
            "# 工具调用格式\n这个模型不支持原生工具调用。\n" + TOOL_PROTOCOL_PROMPT
        )
    parts.append(f"当前画布：{session.canvas_id or '未绑定画布'}")
    return "\n\n".join(part for part in parts if part.strip())
