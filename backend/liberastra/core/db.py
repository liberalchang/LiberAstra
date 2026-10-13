"""数据库引擎与会话。默认 SQLite（WAL 模式），可通过 DATABASE_URL 切换 PostgreSQL。"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from liberastra.core.config import get_settings


def _make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


settings = get_settings()
if settings.resolved_database_url.startswith("sqlite"):
    # SQLite 相对路径数据库文件需要数据目录先存在
    settings.data_dir.mkdir(parents=True, exist_ok=True)
engine = _make_engine(settings.resolved_database_url)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record) -> None:  # noqa: ANN001, ANN202
    if engine.url.get_backend_name() != "sqlite":
        return
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """启动时自动执行 Alembic 迁移（脚本随包分发在 liberastra/alembic/）。"""
    script_location = Path(__file__).resolve().parents[1] / "alembic"
    cfg = Config()
    cfg.set_main_option("script_location", str(script_location))
    cfg.set_main_option("sqlalchemy.url", settings.resolved_database_url)
    command.upgrade(cfg, "head")
