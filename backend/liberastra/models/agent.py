"""导演台会话、消息和技能开关。技能正文放在文件里，表里只记启用状态。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from liberastra.models import Base, utcnow


class AgentSession(Base):
    """一次导演台对话。按画布分开，关掉页面后历史仍在。"""

    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    canvas_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    title: Mapped[str] = mapped_column(String(128), default="新对话")
    provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"), default=None
    )
    model: Mapped[str | None] = mapped_column(String(256), default=None)
    active_skill: Mapped[str] = mapped_column(String(64), default="")
    skill_state: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="idle", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    messages: Mapped[list[AgentMessage]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentMessage.id",
    )


class AgentMessage(Base):
    """一条对话记录。content 是 JSON，可含文本、附件、工具调用和工具结果。"""

    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("agent_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[AgentSession] = relationship(back_populates="messages")


class AgentSkill(Base):
    """技能开关。同名技能在同一用户下唯一；正文在磁盘。"""

    __tablename__ = "agent_skills"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_agent_skill_owner_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(16), default="user")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
