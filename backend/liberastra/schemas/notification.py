"""通知渠道/规则/投递的请求响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ChannelType = Literal["telegram", "feishu", "dingtalk", "bark", "webhook"]
CHANNEL_TYPES: tuple[str, ...] = ("telegram", "feishu", "dingtalk", "bark", "webhook")
ALLOWED_EVENTS: tuple[str, ...] = (
    "job.succeeded",
    "job.failed",
    "job.canceled",
    "job.progress",
)


class NotificationChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    type: ChannelType
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_seconds: int = Field(default=30, ge=1, le=3600)
    timeout_seconds: int = Field(default=10, ge=1, le=60)


class NotificationChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    config: dict[str, Any] | None = None
    clear_secret: bool = False
    enabled: bool | None = None
    max_attempts: int | None = Field(default=None, ge=1, le=10)
    backoff_seconds: int | None = Field(default=None, ge=1, le=3600)
    timeout_seconds: int | None = Field(default=None, ge=1, le=60)


class NotificationChannelOut(BaseModel):
    id: int
    type: str
    name: str
    config: dict[str, Any]
    enabled: bool
    max_attempts: int
    backoff_seconds: int
    timeout_seconds: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestSendOut(BaseModel):
    ok: bool
    message: str


class TelegramChatsRequest(BaseModel):
    channel_id: int | None = None
    bot_token: str | None = None
    use_proxy: bool | None = None


class TelegramChatOut(BaseModel):
    id: str
    type: str
    title: str


class TelegramChatsOut(BaseModel):
    items: list[TelegramChatOut]


class NotificationRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    events: list[str] = Field(
        default_factory=lambda: ["job.succeeded", "job.failed"]
    )
    progress_interval_seconds: int = Field(default=900, ge=60, le=86400)
    job_kinds: list[str] = Field(default_factory=list)
    max_jobs_per_digest: int = Field(default=10, ge=1, le=50)
    quiet_hours: dict[str, str] | None = None
    include_outputs: bool = True
    template_succeeded: str | None = None
    template_failed: str | None = None
    template_progress: str | None = None
    channel_ids: list[int] = Field(min_length=1)

    @field_validator("events")
    @classmethod
    def _valid_events(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - set(ALLOWED_EVENTS))
        if unknown:
            raise ValueError(f"未知通知事件: {unknown}")
        return list(dict.fromkeys(value))


class NotificationRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    enabled: bool | None = None
    events: list[str] | None = None
    progress_interval_seconds: int | None = Field(default=None, ge=60, le=86400)
    job_kinds: list[str] | None = None
    max_jobs_per_digest: int | None = Field(default=None, ge=1, le=50)
    quiet_hours: dict[str, str] | None = None
    include_outputs: bool | None = None
    template_succeeded: str | None = None
    template_failed: str | None = None
    template_progress: str | None = None
    channel_ids: list[int] | None = Field(default=None, min_length=1)

    @field_validator("events")
    @classmethod
    def _valid_events(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        unknown = sorted(set(value) - set(ALLOWED_EVENTS))
        if unknown:
            raise ValueError(f"未知通知事件: {unknown}")
        return list(dict.fromkeys(value))


class NotificationRuleOut(BaseModel):
    id: int
    name: str
    enabled: bool
    enabled_since: datetime
    events: list[str]
    progress_interval_seconds: int
    job_kinds: list[str]
    max_jobs_per_digest: int
    quiet_hours: dict[str, str] | None
    include_outputs: bool
    template_succeeded: str | None
    template_failed: str | None
    template_progress: str | None
    channel_ids: list[int]
    created_at: datetime
    updated_at: datetime


class NotificationDeliveryOut(BaseModel):
    id: int
    rule_id: int | None
    channel_id: int | None
    job_id: str | None
    event: str
    bucket: str
    title: str
    body: str
    status: str
    attempts: int
    max_attempts: int
    next_attempt_at: datetime | None
    response_status: int | None
    last_error: str | None
    created_at: datetime
    sent_at: datetime | None

    model_config = {"from_attributes": True}


class NotificationDeliveryPage(BaseModel):
    items: list[NotificationDeliveryOut]
    total: int
    limit: int
    offset: int


class NotificationMetaOut(BaseModel):
    channel_types: list[str]
    events: list[str]
    languages: list[str]
    defaults: dict[str, Any]
