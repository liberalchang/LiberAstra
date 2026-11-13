"""校验 liberastra skill 中提到的顶层命令都真实存在。"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "liberastra" / "SKILL.md"
CLI_REF = ROOT / "skills" / "liberastra" / "references" / "cli.md"
DIRECTOR = ROOT / "backend" / "liberastra" / "agent" / "skills" / "director" / "SKILL.md"
CANVAS_AUTO = (
    ROOT / "backend" / "liberastra" / "agent" / "skills" / "canvas-auto" / "SKILL.md"
)
CANVAS_SCHEMA = (
    ROOT
    / "backend"
    / "liberastra"
    / "agent"
    / "skills"
    / "canvas-auto"
    / "references"
    / "canvas-schema.md"
)

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


def test_director_skill_documents_speech_tuning_and_cleanup() -> None:
    text = DIRECTOR.read_text(encoding="utf-8")
    for token in ("ttsTuning", "asrTuning", "vcTuning", "canvas_discard_nodes"):
        assert token in text
    for token in ("TTS", "ASR", "VC"):
        assert token in text


def test_canvas_skill_documents_speech_schema() -> None:
    text = CANVAS_AUTO.read_text(encoding="utf-8") + CANVAS_SCHEMA.read_text(encoding="utf-8")
    for token in ("ttsTuning", "asrTuning", "vcTuning", "canvas_discard_nodes"):
        assert token in text
