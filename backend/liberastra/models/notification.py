"""通知渠道、规则、规则-渠道关系和投递记录。

通知配置按 owner 隔离；单用户第一版里 owner_id 恒为管理员。
渠道 config 以 Fernet 加密后存 Text，API 只返回掩码。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from liberastra.models import Base, utcnow


class NotificationChannel(Base):
    __tablename__ = "notification_channels"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_notification_channels_owner_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(128))
    config_encrypted: Mapped[str] = mapped_column(Text)
    config_version: Mapped[int] = mapped_column(default=1)
    enabled: Mapped[bool] = mapped_column(default=True)
    max_attempts: Mapped[int] = mapped_column(default=3)
    backoff_seconds: Mapped[int] = mapped_column(default=30)
    timeout_seconds: Mapped[int] = mapped_column(default=10)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class NotificationRule(Base):
    __tablename__ = "notification_rules"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_notification_rules_owner_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(default=True)
    enabled_since: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    events: Mapped[list] = mapped_column(JSON, default=list)
    progress_interval_seconds: Mapped[int] = mapped_column(default=900)
    job_kinds: Mapped[list] = mapped_column(JSON, default=list)
    max_jobs_per_digest: Mapped[int] = mapped_column(default=10)
    quiet_hours: Mapped[dict | None] = mapped_column(JSON, default=None)
    include_outputs: Mapped[bool] = mapped_column(default=True)
    template_succeeded: Mapped[str | None] = mapped_column(Text, default=None)
    template_failed: Mapped[str | None] = mapped_column(Text, default=None)
    template_progress: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class NotificationRuleChannel(Base):
    __tablename__ = "notification_rule_channels"

    rule_id: Mapped[int] = mapped_column(
        ForeignKey("notification_rules.id", ondelete="CASCADE"), primary_key=True
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("notification_channels.id", ondelete="CASCADE"), primary_key=True
    )


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        Index("ix_notification_deliveries_claim", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("notification_rules.id", ondelete="SET NULL"), default=None
    )
    channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("notification_channels.id", ondelete="SET NULL"), default=None
    )
    job_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    event: Mapped[str] = mapped_column(String(32))
    bucket: Mapped[str] = mapped_column(String(64), default="")
    dedup_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    locked_by: Mapped[str | None] = mapped_column(String(128), default=None)
    response_status: Mapped[int | None] = mapped_column(default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
