"""astra CLI 配置：~/.liberastra/config.toml（server + token）。

优先级：命令行 --server/--token > 环境变量 LIBERASTRA_SERVER/LIBERASTRA_TOKEN > 配置文件。
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

CONFIG_PATH = Path.home() / ".liberastra" / "config.toml"

DEFAULT_SERVER = "http://localhost:8000"


def load() -> dict:
    if CONFIG_PATH.exists():
        return tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    return {}


def save(server: str, token: str) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(f'server = "{server}"\ntoken = "{token}"\n', encoding="utf-8")


def resolve(server: str | None = None, token: str | None = None) -> tuple[str, str | None]:
    cfg = load()
    resolved_server = (
        server or os.environ.get("LIBERASTRA_SERVER") or cfg.get("server") or DEFAULT_SERVER
    )
    resolved_token = token or os.environ.get("LIBERASTRA_TOKEN") or cfg.get("token")
    return resolved_server.rstrip("/"), resolved_token
