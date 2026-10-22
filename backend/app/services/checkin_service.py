"""确认（我在）业务：状态计算、确认落库、历史查询。"""

from __future__ import annotations

import base64
import json
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.models import Account, CheckinRecord, CheckinSetting, Guardian, SafetyAlert
from app.models.enums import CheckinStage, SafetyAlertStatus
from app.schemas.checkin import (
    CheckinCreateRequest,
    CheckinHistoryResponse,
    CheckinRecordRead,
    CheckinStatusRead,
    OpenAlertRead,
    ReminderSlotRead,
)
from app.services.alert_service import resolve_open_alerts
from app.services.schedule import compute_schedule
from app.services.setting_service import get_setting
from app.services.timeutil import iso_local, now_utc, resolve_tz

logger = get_logger(__name__)

STAGE_HINTS: dict[CheckinStage, str] = {
    CheckinStage.NORMAL: "状态正常，下次确认时间前点一下「我在」就好",
    CheckinStage.PENDING: "已到确认时间，点一下「我在」让守护人放心",
    CheckinStage.REMINDING: "还没收到你的确认，我们正在提醒你",
    CheckinStage.ALERT: "已长时间未确认，守护人已收到提醒邮件；点一下「我在」即可恢复正常",
}


def last_checkin_at(session: Session, account_id: int) -> datetime | None:
    value = session.exec(
        select(func.max(CheckinRecord.checked_in_at)).where(
            CheckinRecord.account_id == account_id
        )
    ).one()
    return value


def anchor_for(account: Account, last_at: datetime | None) -> datetime:
    return last_at or account.created_at


def count_guardians(session: Session, account_id: int) -> int:
    return int(
        session.exec(
            select(func.count()).select_from(Guardian).where(Guardian.account_id == account_id)
        ).one()
        or 0
    )


def get_open_alert(session: Session, account_id: int) -> SafetyAlert | None:
    return session.exec(
        select(SafetyAlert)
        .where(
            SafetyAlert.account_id == account_id,
            SafetyAlert.status == SafetyAlertStatus.OPEN.value,
        )
        .order_by(SafetyAlert.triggered_at.desc())  # type: ignore[attr-defined]
    ).first()


def build_status(
    session: Session,
    account: Account,
    setting: CheckinSetting | None = None,
    *,
    now: datetime | None = None,
) -> CheckinStatusRead:
    current = now or now_utc()
    config = setting or get_setting(session, account)
    last_at = last_checkin_at(session, account.id)  # type: ignore[arg-type]
    anchor = anchor_for(account, last_at)

    state = compute_schedule(
        anchor_at=anchor,
        period_days=config.period_days,
        checkin_time_local=config.checkin_time_local,
        timezone=config.timezone,
        reminder_offsets=config.reminder_offsets_safe(),
        alert_offset_minutes=config.alert_offset_minutes,
        now=current,
        reminders_enabled=config.reminders_enabled,
    )
    tz = resolve_tz(config.timezone)
    open_alert = get_open_alert(session, account.id)  # type: ignore[arg-type]

    reminders = [
        ReminderSlotRead(
            index=slot.index,
            offset_minutes=slot.offset_minutes,
            at=slot.at,
            local_at=iso_local(slot.at, tz) or "",
            passed=slot.passed,
            label=f"第 {slot.index} 次提醒",
        )
        for slot in state.reminders
    ]

    return CheckinStatusRead(
        stage=state.stage,
        server_time=current,
        timezone=config.timezone,
        period_days=config.period_days,
        checkin_time=config.checkin_time_local,
        last_checkin_at=last_at,
        next_checkin_at=state.due_at,
        alert_at=state.alert_at,
        seconds_until_due=state.seconds_until_due,
        overdue_seconds=state.overdue_seconds,
        next_reminder_at=state.next_reminder_at,
        reminders_passed=state.reminders_passed,
        reminders=reminders,
        progress_ratio=state.progress_ratio,
        guardian_count=count_guardians(session, account.id),  # type: ignore[arg-type]
        has_open_alert=open_alert is not None,
        open_alert=(
            OpenAlertRead(
                id=open_alert.id,  # type: ignore[arg-type]
                due_at=open_alert.due_at,
                triggered_at=open_alert.triggered_at,
                overdue_minutes=open_alert.overdue_minutes,
                guardian_count=open_alert.guardian_count,
            )
            if open_alert
            else None
        ),
        stage_hint=STAGE_HINTS[state.stage],
    )


def _to_record_read(record: CheckinRecord) -> CheckinRecordRead:
    return CheckinRecordRead(
        id=record.id,  # type: ignore[arg-type]
        checked_in_at=record.checked_in_at,
        client_time=record.client_time,
        due_at=record.due_at,
        source=record.source,
        note=record.note,
    )


def find_by_idempotency_key(
    session: Session, account_id: int, key: str
) -> CheckinRecord | None:
    return session.exec(
        select(CheckinRecord).where(
            CheckinRecord.account_id == account_id,
            CheckinRecord.idempotency_key == key,
        )
    ).first()


def create_checkin(
    session: Session,
    account: Account,
    payload: CheckinCreateRequest,
    *,
    now: datetime | None = None,
) -> tuple[CheckinRecord, bool, int]:
    """执行「我在」确认。

    - 以 ``(account_id, request_id)`` 唯一约束实现幂等，重复请求返回原记录
    - 时间一律使用服务端时间，客户端上报时间仅做展示
    - 返回 (记录, 是否重复, 被解除的异常事件数量)
    """
    current = now or now_utc()

    existing = find_by_idempotency_key(session, account.id, payload.request_id)  # type: ignore[arg-type]
    if existing is not None:
        logger.info("确认请求重复，返回既有记录 id=%s", existing.id)
        return existing, True, 0

    setting = get_setting(session, account)
    last_at = last_checkin_at(session, account.id)  # type: ignore[arg-type]
    anchor = anchor_for(account, last_at)
    state = compute_schedule(
        anchor_at=anchor,
        period_days=setting.period_days,
        checkin_time_local=setting.checkin_time_local,
        timezone=setting.timezone,
        reminder_offsets=setting.reminder_offsets_safe(),
        alert_offset_minutes=setting.alert_offset_minutes,
        now=current,
        reminders_enabled=setting.reminders_enabled,
    )

    record = CheckinRecord(
        account_id=account.id,
        checked_in_at=current,
        client_time=payload.client_time,
        due_at=state.due_at,
        idempotency_key=payload.request_id,
        note=payload.note,
    )
    session.add(record)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        duplicated = find_by_idempotency_key(session, account.id, payload.request_id)  # type: ignore[arg-type]
        if duplicated is None:
            raise
        logger.info("并发确认请求，返回既有记录 id=%s", duplicated.id)
        return duplicated, True, 0

    session.refresh(record)
    resolved = resolve_open_alerts(session, account.id, resolved_at=current)  # type: ignore[arg-type]
    logger.info(
        "确认成功 account_id=%s stage_before=%s resolved_alerts=%s",
        account.public_id,
        state.stage.value,
        resolved,
    )
    return record, False, resolved


def _decode_cursor(cursor: str | None) -> tuple[datetime, int] | None:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8") + b"=" * (-len(cursor) % 4))
        data = json.loads(raw.decode("utf-8"))
        return datetime.fromisoformat(data["t"]), int(data["id"])
    except Exception as exc:  # noqa: BLE001
        raise ValidationError("分页游标无效") from exc


def _encode_cursor(record: CheckinRecord) -> str:
    payload = json.dumps({"t": record.checked_in_at.isoformat(), "id": record.id})
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8").rstrip("=")


def list_history(
    session: Session,
    account: Account,
    *,
    limit: int = 20,
    cursor: str | None = None,
) -> CheckinHistoryResponse:
    from sqlalchemy import or_  # 局部导入，避免污染模块命名空间

    limit = max(1, min(limit, 100))
    stmt = select(CheckinRecord).where(CheckinRecord.account_id == account.id)
    decoded = _decode_cursor(cursor)
    if decoded is not None:
        cursor_time, cursor_id = decoded
        stmt = stmt.where(
            or_(
                CheckinRecord.checked_in_at < cursor_time,
                (CheckinRecord.checked_in_at == cursor_time) & (CheckinRecord.id < cursor_id),
            )
        )
    stmt = stmt.order_by(
        CheckinRecord.checked_in_at.desc(), CheckinRecord.id.desc()  # type: ignore[attr-defined]
    ).limit(limit + 1)

    rows = list(session.exec(stmt).all())
    has_more = len(rows) > limit
    items = rows[:limit]
    return CheckinHistoryResponse(
        items=[_to_record_read(item) for item in items],
        next_cursor=_encode_cursor(items[-1]) if has_more and items else None,
        has_more=has_more,
    )
