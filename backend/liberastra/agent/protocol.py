"""不支持原生工具调用的模型：解析文本协议里的 <tool_call> 块。"""

from __future__ import annotations

import json
import re
from typing import Any

_JSON_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
_XML_CALL_RE = re.compile(
    r"<tool_call>\s*<function=([^>\s]+)\s*>(.*?)</function>\s*</tool_call>",
    re.DOTALL,
)
_XML_PARAM_RE = re.compile(
    r"<parameter=([^>\s]+)\s*>(.*?)</parameter>", re.DOTALL
)
_THINK_RE = re.compile(r"<think>.*?</think>|</?think>", re.DOTALL)


def _xml_value(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def parse_text_tool_calls(text: str) -> tuple[str, list[dict[str, str]]]:
    """从正文里取出工具调用，返回（去掉标签的正文, 调用列表）。

    兼容两种文本协议：JSON 的 <tool_call>{"name":...}</tool_call>，
    以及 Qwen 常见的 <function=工具名><parameter=键>值</parameter></function>。
    """
    found: list[tuple[int, int, dict[str, str]]] = []

    for match in _JSON_CALL_RE.finditer(text):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        name = str(payload.get("name") or "").strip()
        if not name:
            continue
        arguments: Any = payload.get("arguments")
        if arguments is None:
            arguments = {}
        found.append(
            (
                match.start(),
                match.end(),
                {
                    "name": name,
                    "arguments": arguments
                    if isinstance(arguments, str)
                    else json.dumps(arguments, ensure_ascii=False),
                },
            )
        )

    for match in _XML_CALL_RE.finditer(text):
        arguments = {
            param.group(1): _xml_value(param.group(2))
            for param in _XML_PARAM_RE.finditer(match.group(2))
        }
        found.append(
            (
                match.start(),
                match.end(),
                {
                    "name": match.group(1),
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            )
        )

    found.sort(key=lambda item: item[0])
    parts: list[str] = []
    calls: list[dict[str, str]] = []
    cursor = 0
    for start, end, call in found:
        parts.append(text[cursor:start])
        cursor = end
        calls.append({"id": f"text_call_{len(calls)}", **call})
    parts.append(text[cursor:])
    cleaned = _THINK_RE.sub("", "".join(parts)).strip()
    return cleaned, calls


TOOL_PROTOCOL_PROMPT = """如果需要调用工具，必须只输出下面这种格式，一次可以输出多个：
<tool_call>{"name":"工具名","arguments":{...}}</tool_call>
工具调用之外可以写一句简短说明。不要伪造工具结果。"""
