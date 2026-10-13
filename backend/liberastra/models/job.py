"""统一任务模型 Job：所有生成都走 Job；同步接口只是“提交后等待”。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from liberastra.models import Base, utcnow

if TYPE_CHECKING:
    from liberastra.models.asset import Asset
    from liberastra.models.provider import Provider

JOB_STATUSES = ("pending", "running", "succeeded", "failed", "canceled")
TERMINAL_STATUSES = ("succeeded", "failed", "canceled")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kind: Mapped[str] = mapped_column(String(64), index=True)  # 能力或流水线，如 llm.chat
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"), default=None
    )
    model: Mapped[str | None] = mapped_column(String(256), default=None)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    outputs: Mapped[list] = mapped_column(JSON, default=list)  # Asset 引用或内联结果
    error: Mapped[str | None] = mapped_column(Text, default=None)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    provider: Mapped[Provider | None] = relationship(back_populates="jobs")
    assets: Mapped[list[Asset]] = relationship(back_populates="job")
