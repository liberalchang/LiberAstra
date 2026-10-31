"""应用配置。

优先级：环境变量 > .env 文件 > 默认值。
数据库 URL 与主密钥同时接受 ``DATABASE_URL`` / ``LIBERASTRA_SECRET_KEY`` 两种环境变量名。
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LIBERASTRA_", env_file=".env", extra="ignore")

    # 进程内缓存。密钥文件放在同步盘上时，每次请求重读会遇到 Errno 22，认证接口全部 500。
    _cached_secret_key: str | None = PrivateAttr(default=None)

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

    # 单个媒体上传上限（MB），与 ComfyUI 默认 --max-upload-size 100 一致。超过则在发出请求前拒绝。
    comfy_max_upload_mb: int = 100

    cors_origins: list[str] = ["http://127.0.0.1:5173"]
    # 自托管场景：允许局域网 IP、主机名以任意端口打开页面后调用 API
    cors_origin_regex: str = r"https?://.+"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'liberastra.db').as_posix()}"

    @property
    def resolved_secret_key(self) -> str:
        """主密钥：环境变量优先，否则生成并持久化到 data_dir/.secret_key。

        成功读到后缓存在进程内。同步盘会让后续 open() 返回 Errno 22，
        不能在每次鉴权时重新读文件。
        """
        if self.secret_key:
            return self.secret_key
        if self._cached_secret_key:
            return self._cached_secret_key
        key_file = self.data_dir / ".secret_key"
        if key_file.exists():
            key = key_file.read_text(encoding="utf-8").strip()
        else:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            key = secrets.token_urlsafe(48)
            key_file.write_text(key, encoding="utf-8")
        self._cached_secret_key = key
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
