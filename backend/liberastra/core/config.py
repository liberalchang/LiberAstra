"""应用配置。

优先级：环境变量 > .env 文件 > 默认值。
数据库 URL 与主密钥同时接受 ``DATABASE_URL`` / ``LIBERASTRA_SECRET_KEY`` 两种环境变量名。
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LIBERASTRA_", env_file=".env", extra="ignore")

    app_name: str = "LiberAstra"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    data_dir: Path = Path("data")

    database_url: str | None = Field(
        default=None, validation_alias=AliasChoices("LIBERASTRA_DATABASE_URL", "DATABASE_URL")
    )
    secret_key: str | None = Field(
        default=None, validation_alias=AliasChoices("LIBERASTRA_SECRET_KEY", "SECRET_KEY")
    )

    # 前端构建产物目录；缺省时依次尝试 env、<cwd>/frontend/dist、仓库内 frontend/dist
    static_dir: Path | None = None

    access_token_expire_minutes: int = 60 * 12

    # 清理策略：已结束任务及其产物保留天数，0 = 不自动清理
    cleanup_retention_days: int = 0

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'liberastra.db').as_posix()}"

    @property
    def resolved_secret_key(self) -> str:
        """主密钥：环境变量优先，否则生成并持久化到 data_dir/.secret_key。"""
        if self.secret_key:
            return self.secret_key
        key_file = self.data_dir / ".secret_key"
        if key_file.exists():
            return key_file.read_text(encoding="utf-8").strip()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        key = secrets.token_urlsafe(48)
        key_file.write_text(key, encoding="utf-8")
        return key

    @property
    def resolved_static_dir(self) -> Path | None:
        candidates = [
            self.static_dir,
            Path.cwd() / "frontend" / "dist",
            Path(__file__).resolve().parents[3] / "frontend" / "dist",
        ]
        for candidate in candidates:
            if candidate and (candidate / "index.html").exists():
                return candidate
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
