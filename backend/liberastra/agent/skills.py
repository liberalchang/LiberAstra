"""Agent Skills 标准技能包：SKILL.md + 任意可选资源。

技能本身不做文件类型或脚本限制；执行脚本、删除、生成等风险由 agent 安全路由处理。
这里只保留路径穿越、压缩包解压大小和文件数量等资源保护。
"""

from __future__ import annotations

import io
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from liberastra.core.config import get_settings
from liberastra.models import AgentSkill

NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
DESCRIPTION_MAX = 1024
COMPATIBILITY_MAX = 500
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_FILES = 1000
BUILTIN_NAMES = frozenset(
    {"director", "canvas-auto", "skill-creator", "liberastra", "project-info"}
)
_FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".htm",
    ".css",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".py",
    ".sh",
    ".bash",
    ".ps1",
    ".bat",
    ".cmd",
    ".rb",
    ".pl",
    ".php",
    ".sql",
    ".csv",
    ".tsv",
    ".xml",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
}


class SkillError(Exception):
    """技能包格式或内容不合规。"""


def _builtin_root() -> Path:
    return Path(__file__).resolve().parent / "skills"


def _user_root() -> Path:
    return get_settings().data_dir / "agent" / "skills"


def _normalize_path(raw: str) -> str:
    path = str(raw).replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    if not path or path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise SkillError(f"非法文件路径: {raw}")
    parts = [part for part in path.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise SkillError(f"非法文件路径: {raw}")
    return "/".join(parts)


def _valid_name(name: str) -> bool:
    return bool(NAME_RE.match(name)) and "--" not in name


def parse_skill_document(text: str) -> tuple[dict[str, Any], str]:
    """解析标准 frontmatter，返回（元信息, 正文）。"""
    match = _FRONT_MATTER_RE.match(text.lstrip("﻿"))
    if not match:
        raise SkillError("SKILL.md 缺少 YAML front matter（name 和 description）")
    try:
        raw = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise SkillError(f"front matter 不是合法 YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise SkillError("front matter 必须是键值对")
    name = str(raw.get("name") or "").strip()
    description = str(raw.get("description") or "").strip()
    if not _valid_name(name):
        raise SkillError(
            "name 只能用小写字母、数字和连字符，不能以连字符开头/结尾或连续出现连字符，且不超过 64 字"
        )
    if not description:
        raise SkillError("description 不能为空")
    if len(description) > DESCRIPTION_MAX:
        raise SkillError(f"description 不能超过 {DESCRIPTION_MAX} 字")
    meta: dict[str, Any] = {"name": name, "description": description}
    license_text = str(raw.get("license") or "").strip()
    if license_text:
        meta["license"] = license_text
    compatibility = str(raw.get("compatibility") or "").strip()
    if compatibility:
        if len(compatibility) > COMPATIBILITY_MAX:
            raise SkillError(f"compatibility 不能超过 {COMPATIBILITY_MAX} 字")
        meta["compatibility"] = compatibility
    metadata = raw.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise SkillError("metadata 必须是键值对")
        cleaned: dict[str, str] = {}
        for key, value in metadata.items():
            if isinstance(value, (dict, list)):
                raise SkillError("metadata 的值只能是字符串、数字或布尔值")
            cleaned[str(key)] = str(value)
        meta["metadata"] = cleaned
    allowed = raw.get("allowed-tools")
    if allowed is not None:
        if isinstance(allowed, list):
            tools = [str(item).strip() for item in allowed if str(item).strip()]
        elif isinstance(allowed, str):
            tools = allowed.split()
        else:
            raise SkillError("allowed-tools 必须是空格分隔的字符串或列表")
        if tools:
            meta["allowed_tools"] = tools
    body = text[match.end() :].strip()
    return meta, body


def validate_skill_files(files: dict[str, bytes]) -> tuple[str, str]:
    """校验整包技能文件。返回（name, description）；不合规抛 SkillError。"""
    if not files:
        raise SkillError("技能包为空")
    normalized: dict[str, bytes] = {}
    total = 0
    for raw, content in files.items():
        path = _normalize_path(raw)
        if not isinstance(content, bytes):
            content = bytes(content)
        if len(content) > MAX_FILE_BYTES:
            raise SkillError(f"{path} 超过单文件大小上限 {MAX_FILE_BYTES // (1024 * 1024)}MB")
        total += len(content)
        if total > MAX_TOTAL_BYTES:
            raise SkillError(
                f"技能包总大小超过 {MAX_TOTAL_BYTES // (1024 * 1024)}MB"
            )
        normalized[path] = content
    if len(normalized) > MAX_FILES:
        raise SkillError(f"技能包文件数超过 {MAX_FILES}")
    skill_md = normalized.get("SKILL.md") or normalized.get("skill.md")
    if skill_md is None:
        raise SkillError("技能包必须包含 SKILL.md")
    try:
        text = skill_md.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SkillError("SKILL.md 必须是 UTF-8 文本") from exc
    meta, _body = parse_skill_document(text)
    if meta["name"] in BUILTIN_NAMES:
        raise SkillError(f"技能名 {meta['name']} 与内置技能冲突")
    return meta["name"], meta["description"]


def files_from_zip(payload: bytes) -> dict[str, bytes]:
    """读取 zip 并去掉统一的顶层目录。"""
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise SkillError("不是有效的 zip 文件") from exc
    names: list[str] = []
    contents: dict[str, bytes] = {}
    total = 0
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = info.filename.replace("\\", "/")
        if name.startswith("__MACOSX/") or Path(name).name == ".DS_Store":
            continue
        if info.file_size > MAX_FILE_BYTES:
            raise SkillError(
                f"{name} 超过单文件大小上限 {MAX_FILE_BYTES // (1024 * 1024)}MB"
            )
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise SkillError(f"技能包总大小超过 {MAX_TOTAL_BYTES // (1024 * 1024)}MB")
        if len(names) >= MAX_FILES:
            raise SkillError(f"技能包文件数超过 {MAX_FILES}")
        names.append(name)
        try:
            contents[name] = archive.read(info)
        except (RuntimeError, zipfile.BadZipFile) as exc:
            raise SkillError(f"无法读取压缩包内文件: {name}") from exc
    roots = {name.split("/", 1)[0] for name in names if "/" in name}
    if roots and len(roots) == 1 and len(names) == sum(1 for n in names if "/" in n):
        prefix = roots.pop() + "/"
        contents = {name[len(prefix) :]: data for name, data in contents.items()}
    return contents


def skill_dir(name: str, *, user_only: bool = False) -> Path | None:
    if not _valid_name(str(name)):
        raise SkillError(f"非法技能名: {name}")
    user = _user_root() / name
    if user.is_dir():
        return user
    if user_only:
        return None
    builtin = _builtin_root() / name
    return builtin if builtin.is_dir() else None


def read_skill(name: str) -> tuple[dict[str, Any], str]:
    folder = skill_dir(name)
    if folder is None:
        raise SkillError(f"技能不存在: {name}")
    target = folder / "SKILL.md"
    if not target.is_file():
        raise SkillError(f"技能缺少 SKILL.md: {name}")
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SkillError(f"技能文件无法读取: {name}") from exc
    meta, body = parse_skill_document(text)
    meta["source"] = "user" if folder.is_relative_to(_user_root()) else "builtin"
    return meta, body


def list_skill_files(name: str) -> list[dict[str, Any]]:
    folder = skill_dir(name)
    if folder is None:
        raise SkillError(f"技能不存在: {name}")
    out: list[dict[str, Any]] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(folder).as_posix()
        suffix = path.suffix.lower()
        out.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "is_text": relative == "SKILL.md" or suffix in _TEXT_SUFFIXES,
            }
        )
    return out


def read_skill_file(name: str, path: str) -> str:
    folder = skill_dir(name)
    if folder is None:
        raise SkillError(f"技能不存在: {name}")
    relative = _normalize_path(path)
    target = (folder / relative).resolve()
    if not target.is_relative_to(folder.resolve()) or not target.is_file():
        raise SkillError(f"技能文件不存在: {path}")
    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SkillError(f"技能文件不是 UTF-8 文本: {path}") from exc
    except OSError as exc:
        raise SkillError(f"技能文件无法读取: {path}") from exc


def save_skill_files(files: dict[str, bytes]) -> str:
    name, _description = validate_skill_files(files)
    folder = _user_root() / name
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for raw, content in files.items():
        path = folder / _normalize_path(raw)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return name


def save_skill_text(name: str, description: str, body: str) -> str:
    document = (
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body.strip()}\n"
    ).encode()
    return save_skill_files({"SKILL.md": document})


def save_skill_file(name: str, path: str, content: str) -> str:
    """在已有用户技能包内写入一个文本文件；路径和体积仍受保护。"""
    if not _valid_name(str(name)):
        raise SkillError(f"非法技能名: {name}")
    folder = skill_dir(name, user_only=True)
    if folder is None:
        raise SkillError(f"技能不存在: {name}")
    relative = _normalize_path(path)
    if relative.lower() == "skill.md":
        raise SkillError("SKILL.md 请使用 save_skill 保存，避免绕过元信息校验")
    data = content.encode("utf-8")
    if len(data) > MAX_FILE_BYTES:
        raise SkillError(f"{relative} 超过单文件大小上限")
    target = (folder / relative).resolve()
    if not target.is_relative_to(folder.resolve()):
        raise SkillError(f"非法文件路径: {path}")
    existing = target.stat().st_size if target.is_file() else 0
    total = sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())
    if total - existing + len(data) > MAX_TOTAL_BYTES:
        raise SkillError(f"技能包总大小超过 {MAX_TOTAL_BYTES // (1024 * 1024)}MB")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return relative


def _skill_meta(folder: Path) -> tuple[dict[str, Any], str] | None:
    target = folder / "SKILL.md"
    if not target.is_file():
        return None
    try:
        return parse_skill_document(target.read_text(encoding="utf-8"))
    except (SkillError, OSError, UnicodeDecodeError):
        return None


def list_skill_summaries(db: Session, owner_id: int) -> list[dict[str, Any]]:
    overrides = {
        row.name: row
        for row in db.scalars(select(AgentSkill).where(AgentSkill.owner_id == owner_id)).all()
    }
    folders: dict[str, Path] = {}
    for root in (_builtin_root(), _user_root()):
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if child.is_dir() and _valid_name(child.name):
                folders[child.name] = child
    out: list[dict[str, Any]] = []
    for name, folder in folders.items():
        parsed = _skill_meta(folder)
        if parsed is None:
            continue
        meta, _body = parsed
        row = overrides.get(name)
        files = [path for path in folder.rglob("*") if path.is_file()]
        has_scripts = any(
            path.relative_to(folder).as_posix().startswith("scripts/") for path in files
        )
        out.append(
            {
                "name": meta["name"],
                "description": meta["description"],
                "source": "user" if folder.is_relative_to(_user_root()) else "builtin",
                "builtin": name in BUILTIN_NAMES,
                "enabled": bool(row.enabled) if row is not None else True,
                "version": int(row.version) if row is not None else 1,
                "license": meta.get("license", ""),
                "compatibility": meta.get("compatibility", ""),
                "allowed_tools": list(meta.get("allowed_tools") or []),
                "file_count": len(files),
                "has_scripts": has_scripts,
            }
        )
    out.sort(key=lambda item: (not item["builtin"], item["name"]))
    return out
