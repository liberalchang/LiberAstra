"""Asset 资产模型：图片、音频、视频、字幕、文本，作品库的统一载体。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from liberastra.models import Base, utcnow

if TYPE_CHECKING:
    from liberastra.models.job import Job

ASSET_KINDS = ("image", "audio", "video", "subtitle", "text")
ASSET_ORIGINS = ("upload", "output", "character", "canvas")


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        Index(
            "ix_assets_owner_hidden_kind_created",
            "owner_id",
            "hidden",
            "kind",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    path: Mapped[str] = mapped_column(String(512))  # 相对数据目录的路径
    mime: Mapped[str | None] = mapped_column(String(128), default=None)
    size: Mapped[int] = mapped_column(default=0)
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), default=None, index=True
    )
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    # 来源：上传、任务产出、角色库、画布/功能页临时资源。角色库资源不进资产库。
    origin: Mapped[str] = mapped_column(
        String(16), default="output", server_default="output", index=True
    )
    # 画布中间结果打标隐藏：资源库默认不显示，发布后转正
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job | None] = relationship(back_populates="assets")
