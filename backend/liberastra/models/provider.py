"""Provider 模型：外部服务提供方配置。api_key 以 Fernet 加密落库。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from liberastra.models import Base, utcnow

if TYPE_CHECKING:
    from liberastra.models.job import Job


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    type: Mapped[str] = mapped_column(String(64), index=True)
    base_url: Mapped[str] = mapped_column(String(512), default="")
    api_key_encrypted: Mapped[str | None] = mapped_column(String(1024), default=None)
    models: Mapped[list[str]] = mapped_column(JSON, default=list)  # 缓存的模型列表
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    concurrency: Mapped[int] = mapped_column(default=2)  # 该 Provider 的任务并发上限
    enabled: Mapped[bool] = mapped_column(default=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)  # 额外配置（自定义 headers 等）
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    jobs: Mapped[list[Job]] = relationship(back_populates="provider")
