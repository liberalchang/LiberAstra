"""工具安全路由：按风险决定自动执行、暂停确认或拒绝。

策略存在会话的 skill_state["safety"] 中：
- auto: 本会话自动允许的工具名
风险较高的删除、生成、脚本和文件写入默认暂停，用户在确认卡里选择一次执行或本会话自动。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

READ = "read"
CANVAS_WRITE = "canvas_write"
FILE_WRITE = "file_write"
DESTRUCTIVE = "destructive"
GENERATE = "generate"
SCRIPT = "script"
UNKNOWN = "unknown"

CONFIRM_RISKS = {FILE_WRITE, DESTRUCTIVE, GENERATE, SCRIPT, UNKNOWN}

TOOL_RISKS: dict[str, str] = {
    "ask_user": READ,
    "load_skill": READ,
    "read_skill_file": READ,
    "list_skill_files": READ,
    "update_session_state": READ,
    "list_assets": READ,
    "get_asset": READ,
    "read_asset_text": READ,
    "list_characters": READ,
    "list_canvas_menu": READ,
    "list_workflows": READ,
    "list_execution_specs": READ,
    "list_voices": READ,
    "list_music": READ,
    "canvas_get_graph": READ,
    "canvas_get_node": READ,
    "canvas_get_node_schema": READ,
    "canvas_add_node": CANVAS_WRITE,
    "canvas_apply_menu": CANVAS_WRITE,
    "canvas_apply_pack": CANVAS_WRITE,
    "canvas_update_node": CANVAS_WRITE,
    "canvas_connect": CANVAS_WRITE,
    "canvas_disconnect": CANVAS_WRITE,
    "canvas_set_binding": CANVAS_WRITE,
    "canvas_layout": CANVAS_WRITE,
    "canvas_delete_nodes": DESTRUCTIVE,
    "canvas_run_nodes": GENERATE,
    "generate_image": GENERATE,
    "edit_image": GENERATE,
    "generate_video": GENERATE,
    "tts": GENERATE,
    "asr": GENERATE,
    "create_character": GENERATE,
    "save_skill": FILE_WRITE,
    "save_skill_file": FILE_WRITE,
    "run_skill_script": SCRIPT,
}

RISK_TITLES = {
    CANVAS_WRITE: "Agent 想修改画布",
    FILE_WRITE: "Agent 想写入技能文件",
    DESTRUCTIVE: "Agent 想删除或覆盖内容",
    GENERATE: "Agent 想提交生成任务（占用 GPU）",
    SCRIPT: "Agent 想运行技能脚本",
    UNKNOWN: "Agent 想执行未分类操作",
}

TOOL_TITLES = {
    "canvas_delete_nodes": "Agent 想删除画布节点",
    "canvas_run_nodes": "Agent 想执行画布节点",
    "save_skill": "Agent 想写入技能文件",
    "save_skill_file": "Agent 想写入技能文件",
    "run_skill_script": "Agent 想运行技能脚本",
}


@dataclass(frozen=True)
class SafetyDecision:
    action: str
    risk: str
    title: str

    @property
    def requires_confirm(self) -> bool:
        return self.action == "confirm"


def _policy(session: Any) -> dict[str, Any]:
    state = getattr(session, "skill_state", None) or {}
    policy = state.get("safety") if isinstance(state, dict) else None
    return dict(policy) if isinstance(policy, dict) else {}


def _auto_set(session: Any) -> set[str]:
    return {str(item) for item in (_policy(session).get("auto") or [])}


def decide_tool(session: Any, name: str) -> SafetyDecision:
    risk = TOOL_RISKS.get(str(name), UNKNOWN)
    title = TOOL_TITLES.get(str(name)) or RISK_TITLES.get(risk, RISK_TITLES[UNKNOWN])
    auto = _auto_set(session)
    if str(name) in auto or risk in auto:
        return SafetyDecision("allow", risk, title)
    if risk not in CONFIRM_RISKS:
        return SafetyDecision("allow", risk, title)
    return SafetyDecision("confirm", risk, title)


def remember_auto(session: Any, names: list[str]) -> list[str]:
    state = dict(getattr(session, "skill_state", None) or {})
    safety = dict(state.get("safety") or {})
    current = {str(item) for item in (safety.get("auto") or [])}
    current.update(str(name) for name in names if name)
    safety["auto"] = sorted(current)
    state["safety"] = safety
    session.skill_state = state
    return safety["auto"]


def policy_view(session: Any) -> dict[str, Any]:
    policy = _policy(session)
    return {"auto": list(policy.get("auto") or [])}
