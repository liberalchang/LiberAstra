"""校验 liberastra skill 中提到的顶层命令都真实存在。"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "liberastra" / "SKILL.md"
CLI_REF = ROOT / "skills" / "liberastra" / "references" / "cli.md"

KNOWN_COMMANDS = {
    "serve",
    "doctor",
    "version",
    "logout",
    "login",
    "config",
    "tts",
    "asr",
    "mcp",
    "provider",
    "image",
    "video",
    "job",
    "workflow",
    "asset",
    "voices",
}


def test_skill_frontmatter() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "name: liberastra" in text
    assert "description:" in text


def test_skill_commands_exist() -> None:
    text = SKILL.read_text(encoding="utf-8") + CLI_REF.read_text(encoding="utf-8")
    commands = set(re.findall(r"\bastra\s+([a-z][a-z-]*)", text))
    unknown = commands - KNOWN_COMMANDS
    assert not unknown, f"unknown astra commands in skill docs: {sorted(unknown)}"
