"""Character 角色库：保存角色外观、三视图和拆开的单视角图。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from liberastra.models import Base, utcnow


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    portrait_path: Mapped[str | None] = mapped_column(String(512), default=None)
    turnaround_path: Mapped[str | None] = mapped_column(String(512), default=None)
    front_path: Mapped[str | None] = mapped_column(String(512), default=None)
    side_path: Mapped[str | None] = mapped_column(String(512), default=None)
    back_path: Mapped[str | None] = mapped_column(String(512), default=None)
    voice_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("voices.id", ondelete="SET NULL"), default=None
    )
    voice_name: Mapped[str | None] = mapped_column(String(256), default=None)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
