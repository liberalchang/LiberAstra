"""运行技能包 scripts/ 内的脚本。

脚本以 LiberAstra 后端进程权限执行，没有操作系统级沙箱；调用方必须先经过安全路由确认。
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path

from liberastra.agent.skills import SkillError, _normalize_path, skill_dir

MAX_TIMEOUT = 120
MAX_OUTPUT = 60_000
MAX_ARGS = 50
MAX_ARG_CHARS = 2_000
_SAFE_ENV_KEYS = (
    "PATH",
    "SYSTEMROOT",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "LANG",
)


def _which(command: str) -> str:
    found = shutil.which(command)
    if not found:
        raise SkillError(f"运行环境缺少 {command}")
    return found


def _command(script: Path) -> list[str]:
    suffix = script.suffix.lower()
    if suffix == ".py":
        return [sys.executable, str(script)]
    if suffix in {".sh", ".bash"}:
        return [_which("bash"), str(script)]
    if suffix in {".js", ".mjs", ".cjs"}:
        return [_which("node"), str(script)]
    if suffix == ".ps1":
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            raise SkillError("运行环境缺少 PowerShell")
        return [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    if suffix in {".bat", ".cmd"}:
        return [os.environ.get("COMSPEC") or "cmd.exe", "/c", str(script)]
    raise SkillError(
        f"不支持的脚本类型: {script.name}（支持 .py/.sh/.js/.ps1/.bat/.cmd）"
    )


def _safe_env() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key in _SAFE_ENV_KEYS or key.startswith("LC_")
    }
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _clean_args(args: list[str] | None) -> list[str]:
    if not args:
        return []
    if len(args) > MAX_ARGS:
        raise SkillError(f"脚本参数不能超过 {MAX_ARGS} 个")
    cleaned = []
    for item in args:
        text = str(item)
        if len(text) > MAX_ARG_CHARS:
            raise SkillError(f"单个脚本参数不能超过 {MAX_ARG_CHARS} 字")
        cleaned.append(text)
    return cleaned


async def run_skill_script(
    name: str,
    script: str,
    args: list[str] | None = None,
    *,
    timeout: int = 60,
) -> dict[str, object]:
    folder = skill_dir(name)
    if folder is None:
        raise SkillError(f"技能不存在: {name}")
    relative = _normalize_path(script)
    if not relative.lower().startswith("scripts/"):
        raise SkillError("只能运行技能包 scripts/ 目录内的脚本")
    target = (folder / relative).resolve()
    if not target.is_relative_to(folder.resolve()) or not target.is_file():
        raise SkillError(f"脚本不存在: {script}")
    seconds = max(1, min(int(timeout or 60), MAX_TIMEOUT))
    command = _command(target)
    process = await asyncio.create_subprocess_exec(
        *command,
        *_clean_args(args),
        cwd=str(folder),
        env=_safe_env(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    timed_out = False
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=seconds)
    except TimeoutError:
        timed_out = True
        process.kill()
        stdout, stderr = await process.communicate()
    return {
        "script": relative,
        "exit_code": process.returncode,
        "stdout": stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT],
        "stderr": stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT],
        "timed_out": timed_out,
    }
