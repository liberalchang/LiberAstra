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


def test_director_documents_video_duration_rules() -> None:
    text = DIRECTOR.read_text(encoding="utf-8")
    assert "duration_rule" in text
    assert "数字人口播" in text
    assert "动作迁移" in text
    assert "压缩文案" in text
    assert "裁短参考视频" in text


def test_avatar_and_motion_manifests_document_auto_duration() -> None:
    workflows = ROOT / "backend" / "workflows"
    for name in (
        "minimax_h3_avatar",
        "minimax_h3_avatar_uncensored",
        "minimax_h3_motion",
        "minimax_h3_motion_uncensored",
    ):
        text = (workflows / name / "manifest.yaml").read_text(encoding="utf-8")
        assert "不采用手动 length" in text, name
        assert "总时长可超过" in text, name


def test_prompt_writing_skills_are_loadable_with_references() -> None:
    from liberastra.agent.skills import list_skill_files, read_skill

    expected = {
        "h3-prompt-writing": {"references/base-en.txt", "references/ref-en.txt"},
        "qwen-image-2-1-prompt-writing": {
            "references/t2i-rules.md",
            "references/edit-rules.md",
            "references/text-rendering.md",
            "references/cheat-sheet.md",
            "references/examples.md",
        },
    }
    for name, references in expected.items():
        meta, body = read_skill(name)
        assert meta["name"] == name
        assert meta["source"] == "builtin"
        assert body.strip()
        files = {item["path"] for item in list_skill_files(name)}
        assert references <= files
