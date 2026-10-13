"""Voice 音色库：持久保存参考音频与文本，以及各 Provider 注册后的 voice_id。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from liberastra.models import Base, utcnow

if TYPE_CHECKING:
    from liberastra.models.provider import Provider


class Voice(Base):
    __tablename__ = "voices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), default=None, index=True
    )
    voice_id: Mapped[str | None] = mapped_column(String(256), default=None)  # 云端复刻返回的 ID
    ref_audio_path: Mapped[str | None] = mapped_column(String(512), default=None)  # 相对数据目录
    ref_text: Mapped[str | None] = mapped_column(Text, default=None)  # 参考音频对应文本
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_default: Mapped[bool] = mapped_column(default=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    provider: Mapped[Provider | None] = relationship()
