"""通知渠道/规则/投递 API。"""

from __future__ import annotations

import re
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.models import (
    NotificationChannel,
    NotificationDelivery,
    NotificationRule,
    NotificationRuleChannel,
    User,
    utcnow,
)
from liberastra.schemas.notification import (
    ALLOWED_EVENTS,
    CHANNEL_TYPES,
    NotificationChannelCreate,
    NotificationChannelOut,
    NotificationChannelUpdate,
    NotificationDeliveryOut,
    NotificationDeliveryPage,
    NotificationMetaOut,
    NotificationRuleCreate,
    NotificationRuleOut,
    NotificationRuleUpdate,
    TelegramChatOut,
    TelegramChatsOut,
    TelegramChatsRequest,
    TestSendOut,
)
from liberastra.services.notifications.adapters import (
    NotificationMessage,
    fetch_telegram_chats,
    send,
)
from liberastra.services.notifications.config import (
    ConfigError,
    decrypt_config,
    encrypt_config,
    mask_config,
    merge_config,
    validate_config,
    validate_telegram_token,
)
from liberastra.services.preferences import get_str_pref

router = APIRouter(prefix="/notifications", tags=["notifications"])

_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def _channel_out(record: NotificationChannel) -> NotificationChannelOut:
    try:
        config = mask_config(record.type, decrypt_config(record.config_encrypted))
    except ConfigError:
        config = {"_error": "配置无法解密，请重新填写"}
    return NotificationChannelOut(
        id=record.id,
        type=record.type,
        name=record.name,
        config=config,
        enabled=record.enabled,
        max_attempts=record.max_attempts,
        backoff_seconds=record.backoff_seconds,
        timeout_seconds=record.timeout_seconds,
        last_error=record.last_error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _get_channel(db, channel_id: int, user: User) -> NotificationChannel:  # noqa: ANN001
    record = db.get(NotificationChannel, channel_id)
    if record is None or record.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知渠道不存在")
    return record


def _get_rule(db, rule_id: int, user: User) -> NotificationRule:  # noqa: ANN001
    record = db.get(NotificationRule, rule_id)
    if record is None or record.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知规则不存在")
    return record


def _channel_ids(db, rule_id: int) -> list[int]:  # noqa: ANN001
    return list(
        db.scalars(
            select(NotificationRuleChannel.channel_id)
            .where(NotificationRuleChannel.rule_id == rule_id)
            .order_by(NotificationRuleChannel.channel_id)
        ).all()
    )


def _rule_out(db, record: NotificationRule) -> NotificationRuleOut:  # noqa: ANN001
    return NotificationRuleOut(
        id=record.id,
        name=record.name,
        enabled=record.enabled,
        enabled_since=record.enabled_since,
        events=list(record.events or []),
        progress_interval_seconds=record.progress_interval_seconds,
        job_kinds=list(record.job_kinds or []),
        max_jobs_per_digest=record.max_jobs_per_digest,
        quiet_hours=record.quiet_hours,
        include_outputs=record.include_outputs,
        template_succeeded=record.template_succeeded,
        template_failed=record.template_failed,
        template_progress=record.template_progress,
        channel_ids=_channel_ids(db, record.id),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _validate_channel_ids(db, owner_id: int, channel_ids: list[int]) -> list[int]:  # noqa: ANN001
    wanted = list(dict.fromkeys(int(value) for value in channel_ids))
    if not wanted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少选择一个渠道")
    rows = db.scalars(
        select(NotificationChannel).where(
            NotificationChannel.owner_id == owner_id,
            NotificationChannel.id.in_(wanted),
        )
    ).all()
    found = {row.id for row in rows}
    missing = [value for value in wanted if value not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"渠道不存在: {missing}"
        )
    return wanted


def _validate_quiet_hours(value: dict[str, str] | None) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="quiet_hours 格式不正确")
    start = str(value.get("start") or "")
    end = str(value.get("end") or "")
    tz = str(value.get("timezone") or "")
    if not _TIME_RE.match(start) or not _TIME_RE.match(end):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="静默时段需为 HH:MM")
    try:
        datetime.strptime(start, "%H:%M")
        datetime.strptime(end, "%H:%M")
        ZoneInfo(tz)
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="静默时段时区或时间不合法"
        ) from exc
    return {"start": start, "end": end, "timezone": tz}


def _test_message(language: str) -> NotificationMessage:
    if language == "en":
        return NotificationMessage(
            title="LiberAstra notification test",
            body="This is a test notification. If you can read this, the channel is working.",
            event="test",
        )
    return NotificationMessage(
        title="LiberAstra 通知测试",
        body="这是一条测试通知。能收到说明渠道配置有效。",
        event="test",
    )


def _test_delivery(
    channel: NotificationChannel,
    user: User,
    message: NotificationMessage,
    *,
    ok: bool,
    error: str | None,
    response_status: int | None,
) -> NotificationDelivery:
    return NotificationDelivery(
        owner_id=user.id,
        rule_id=None,
        channel_id=channel.id,
        job_id=None,
        event="test",
        bucket="test",
        dedup_key=f"test:{uuid4().hex}",
        title=message.title,
        body=message.body,
        payload=message.payload,
        status="sent" if ok else "failed",
        attempts=1,
        max_attempts=1,
        response_status=response_status,
        last_error=error,
        sent_at=utcnow() if ok else None,
    )


@router.get("/channels", response_model=list[NotificationChannelOut])
def list_channels(user: CurrentUser, db: DbSession) -> list[NotificationChannelOut]:
    records = db.scalars(
        select(NotificationChannel)
        .where(NotificationChannel.owner_id == user.id)
        .order_by(NotificationChannel.id)
    ).all()
    return [_channel_out(record) for record in records]


@router.post(
    "/channels", response_model=NotificationChannelOut, status_code=status.HTTP_201_CREATED
)
def create_channel(
    body: NotificationChannelCreate, user: CurrentUser, db: DbSession
) -> NotificationChannelOut:
    try:
        config = validate_config(body.type, body.config)
    except ConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    record = NotificationChannel(
        owner_id=user.id,
        type=body.type,
        name=body.name.strip(),
        config_encrypted=encrypt_config(config),
        config_version=1,
        enabled=body.enabled,
        max_attempts=body.max_attempts,
        backoff_seconds=body.backoff_seconds,
        timeout_seconds=body.timeout_seconds,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="同名通知渠道已存在"
        ) from exc
    db.refresh(record)
    return _channel_out(record)


@router.patch("/channels/{channel_id}", response_model=NotificationChannelOut)
def update_channel(
    channel_id: int,
    body: NotificationChannelUpdate,
    user: CurrentUser,
    db: DbSession,
) -> NotificationChannelOut:
    record = _get_channel(db, channel_id, user)
    if body.name is not None:
        record.name = body.name.strip()
    if body.config is not None or body.clear_secret:
        try:
            existing = decrypt_config(record.config_encrypted)
            config = merge_config(
                record.type, existing, body.config or {}, clear_secret=body.clear_secret
            )
        except ConfigError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        record.config_encrypted = encrypt_config(config)
    if body.enabled is not None:
        record.enabled = body.enabled
    if body.max_attempts is not None:
        record.max_attempts = body.max_attempts
    if body.backoff_seconds is not None:
        record.backoff_seconds = body.backoff_seconds
    if body.timeout_seconds is not None:
        record.timeout_seconds = body.timeout_seconds
    if body.enabled is False:
        db.execute(
            update(NotificationDelivery)
            .where(
                NotificationDelivery.channel_id == record.id,
                NotificationDelivery.status == "pending",
            )
            .values(status="skipped", last_error="渠道已停用")
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="同名通知渠道已存在"
        ) from exc
    db.refresh(record)
    return _channel_out(record)


@router.delete("/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(channel_id: int, user: CurrentUser, db: DbSession) -> None:
    record = _get_channel(db, channel_id, user)
    db.execute(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.channel_id == record.id,
            NotificationDelivery.status == "pending",
        )
        .values(status="skipped", last_error="渠道已删除")
    )
    db.delete(record)
    db.commit()


@router.post("/channels/{channel_id}/test", response_model=TestSendOut)
async def test_channel(channel_id: int, user: CurrentUser, db: DbSession) -> TestSendOut:
    record = _get_channel(db, channel_id, user)
    language = get_str_pref(db, "notification_language")
    proxy = get_str_pref(db, "notification_proxy") or None
    message = _test_message(language)
    try:
        config = decrypt_config(record.config_encrypted)
    except ConfigError as exc:
        record.last_error = str(exc)
        db.add(
            _test_delivery(
                record, user, message, ok=False, error=str(exc), response_status=None
            )
        )
        db.commit()
        return TestSendOut(ok=False, message=str(exc))

    use_proxy = bool(config.get("use_proxy", True))
    result = await send(
        record.type,
        config,
        message,
        timeout=float(record.timeout_seconds),
        proxy=proxy if use_proxy else None,
        use_proxy=use_proxy,
    )
    record.last_error = None if result.ok else result.message
    db.add(
        _test_delivery(
            record,
            user,
            message,
            ok=result.ok,
            error=None if result.ok else result.message,
            response_status=result.status,
        )
    )
    db.commit()
    if result.ok:
        text = "Test message sent" if language == "en" else "测试消息已发送"
        return TestSendOut(ok=True, message=text)
    return TestSendOut(ok=False, message=result.message)


@router.post("/telegram/chats", response_model=TelegramChatsOut)
async def list_telegram_chats(
    body: TelegramChatsRequest, user: CurrentUser, db: DbSession
) -> TelegramChatsOut:
    token = (body.bot_token or "").strip()
    config: dict | None = None
    timeout = 10.0
    if body.channel_id is not None:
        record = _get_channel(db, body.channel_id, user)
        if record.type != "telegram":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只有 Telegram 渠道可以获取 Chat ID",
            )
        timeout = float(record.timeout_seconds)
        if not token:
            try:
                config = decrypt_config(record.config_encrypted)
            except ConfigError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                ) from exc
            token = str(config.get("bot_token") or "")
    elif not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供 Bot Token 或已保存的 Telegram 渠道",
        )
    try:
        token = validate_telegram_token(token)
    except ConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    use_proxy = (
        body.use_proxy
        if body.use_proxy is not None
        else (bool(config.get("use_proxy", True)) if config is not None else True)
    )
    proxy = get_str_pref(db, "notification_proxy") or None
    result = await fetch_telegram_chats(
        token,
        timeout=timeout,
        proxy=proxy if use_proxy else None,
        use_proxy=use_proxy,
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=result.message
        )
    return TelegramChatsOut(
        items=[
            TelegramChatOut(id=chat.id, type=chat.type, title=chat.title)
            for chat in result.chats
        ]
    )


@router.get("/rules", response_model=list[NotificationRuleOut])
def list_rules(user: CurrentUser, db: DbSession) -> list[NotificationRuleOut]:
    records = db.scalars(
        select(NotificationRule)
        .where(NotificationRule.owner_id == user.id)
        .order_by(NotificationRule.id)
    ).all()
    return [_rule_out(db, record) for record in records]


@router.post(
    "/rules", response_model=NotificationRuleOut, status_code=status.HTTP_201_CREATED
)
def create_rule(
    body: NotificationRuleCreate, user: CurrentUser, db: DbSession
) -> NotificationRuleOut:
    if not body.events:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少选择一个事件")
    channel_ids = _validate_channel_ids(db, user.id, body.channel_ids)
    quiet_hours = _validate_quiet_hours(body.quiet_hours)
    record = NotificationRule(
        owner_id=user.id,
        name=body.name.strip(),
        enabled=body.enabled,
        enabled_since=utcnow(),
        events=body.events,
        progress_interval_seconds=body.progress_interval_seconds,
        job_kinds=list(dict.fromkeys(body.job_kinds)),
        max_jobs_per_digest=body.max_jobs_per_digest,
        quiet_hours=quiet_hours,
        include_outputs=body.include_outputs,
        template_succeeded=body.template_succeeded,
        template_failed=body.template_failed,
        template_progress=body.template_progress,
    )
    db.add(record)
    try:
        db.flush()
        db.add_all(
            [
                NotificationRuleChannel(rule_id=record.id, channel_id=channel_id)
                for channel_id in channel_ids
            ]
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="同名通知规则已存在"
        ) from exc
    db.refresh(record)
    return _rule_out(db, record)


@router.patch("/rules/{rule_id}", response_model=NotificationRuleOut)
def update_rule(
    rule_id: int, body: NotificationRuleUpdate, user: CurrentUser, db: DbSession
) -> NotificationRuleOut:
    record = _get_rule(db, rule_id, user)
    data = body.model_dump(exclude_unset=True)
    channel_ids = data.pop("channel_ids", None)
    if "events" in data and not data["events"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少选择一个事件")
    if "quiet_hours" in data:
        data["quiet_hours"] = _validate_quiet_hours(data["quiet_hours"])
    if "enabled" in data and data["enabled"] and not record.enabled:
        data["enabled_since"] = utcnow()
    for key, value in data.items():
        if key == "job_kinds" and value is not None:
            value = list(dict.fromkeys(value))
        setattr(record, key, value)
    if data.get("enabled") is False:
        db.execute(
            update(NotificationDelivery)
            .where(
                NotificationDelivery.rule_id == record.id,
                NotificationDelivery.status == "pending",
            )
            .values(status="skipped", last_error="规则已停用")
        )
    if channel_ids is not None:
        wanted = _validate_channel_ids(db, user.id, channel_ids)
        db.execute(
            delete(NotificationRuleChannel).where(
                NotificationRuleChannel.rule_id == record.id
            )
        )
        db.add_all(
            [
                NotificationRuleChannel(rule_id=record.id, channel_id=channel_id)
                for channel_id in wanted
            ]
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="同名通知规则已存在"
        ) from exc
    db.refresh(record)
    return _rule_out(db, record)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: int, user: CurrentUser, db: DbSession) -> None:
    record = _get_rule(db, rule_id, user)
    db.execute(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.rule_id == record.id,
            NotificationDelivery.status == "pending",
        )
        .values(status="skipped", last_error="规则已删除")
    )
    db.delete(record)
    db.commit()


@router.get("/deliveries", response_model=NotificationDeliveryPage)
def list_deliveries(
    user: CurrentUser,
    db: DbSession,
    status_filter: str | None = Query(default=None, alias="status"),
    event: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> NotificationDeliveryPage:
    conditions = [NotificationDelivery.owner_id == user.id]
    if status_filter:
        conditions.append(NotificationDelivery.status == status_filter)
    if event:
        conditions.append(NotificationDelivery.event == event)
    total = db.scalar(
        select(func.count()).select_from(NotificationDelivery).where(*conditions)
    ) or 0
    records = db.scalars(
        select(NotificationDelivery)
        .where(*conditions)
        .order_by(NotificationDelivery.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return NotificationDeliveryPage(
        items=[NotificationDeliveryOut.model_validate(record) for record in records],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.post("/deliveries/{delivery_id}/retry", response_model=NotificationDeliveryOut)
def retry_delivery(
    delivery_id: int, user: CurrentUser, db: DbSession
) -> NotificationDeliveryOut:
    record = db.get(NotificationDelivery, delivery_id)
    if record is None or record.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="投递记录不存在")
    if record.status not in ("failed", "skipped"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="只有 failed/skipped 可以重试"
        )
    if record.channel_id is None or db.get(NotificationChannel, record.channel_id) is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="目标渠道已不存在")
    if record.rule_id is not None and db.get(NotificationRule, record.rule_id) is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="目标规则已不存在")
    record.status = "pending"
    record.attempts = 0
    record.next_attempt_at = utcnow()
    record.locked_at = None
    record.locked_by = None
    record.last_error = None
    db.commit()
    db.refresh(record)
    return NotificationDeliveryOut.model_validate(record)


@router.get("/meta", response_model=NotificationMetaOut)
def meta(user: CurrentUser) -> NotificationMetaOut:
    return NotificationMetaOut(
        channel_types=list(CHANNEL_TYPES),
        events=list(ALLOWED_EVENTS),
        languages=["zh-CN", "en"],
        defaults={
            "progress_interval_seconds": 900,
            "min_progress_interval_seconds": 60,
            "max_jobs_per_digest": 10,
            "max_attempts": 3,
            "backoff_seconds": 30,
            "timeout_seconds": 10,
        },
    )
