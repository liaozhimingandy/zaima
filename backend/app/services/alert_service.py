"""异常事件：状态扫描、事件创建与恢复。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.logging import get_logger
from app.models import Account, CheckinRecord, CheckinSetting, Guardian, SafetyAlert
from app.models.enums import AccountStatus, NotificationStatus, SafetyAlertStatus
from app.services.mail.templates import AlertEmailContext, render_alert_email
from app.models.notification import NotificationRecord
from app.services.schedule import compute_schedule
from app.services.timeutil import ensure_utc, now_utc

logger = get_logger(__name__)


@dataclass
class ScanStats:
    scanned: int = 0
    alerts_created: int = 0
    alerts_existing: int = 0
    notifications_created: int = 0
    skipped_no_guardian: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "scanned": self.scanned,
            "alertsCreated": self.alerts_created,
            "alertsExisting": self.alerts_existing,
            "notificationsCreated": self.notifications_created,
            "skippedNoGuardian": self.skipped_no_guardian,
            "errors": self.errors,
        }


def resolve_open_alerts(
    session: Session,
    account_id: uuid.UUID,
    *,
    resolved_at: datetime | None = None,
    resolved_by: str = "checkin",
) -> int:
    """用户重新确认后恢复正常：关闭未处理事件，并取消其待发送通知。"""
    alerts = list(
        session.exec(
            select(SafetyAlert).where(
                SafetyAlert.account_id == account_id,
                SafetyAlert.status == SafetyAlertStatus.OPEN.value,
            )
        ).all()
    )
    if not alerts:
        return 0
    moment = resolved_at or now_utc()
    alert_ids = [alert.id for alert in alerts]
    for alert in alerts:
        alert.status = SafetyAlertStatus.RESOLVED.value
        alert.resolved_at = moment
        alert.resolved_by = resolved_by
        session.add(alert)

    session.exec(  # type: ignore[call-overload]
        update(NotificationRecord)
        .where(
            NotificationRecord.alert_id.in_(alert_ids),  # type: ignore[attr-defined]
            NotificationRecord.status.in_(  # type: ignore[attr-defined]
                [NotificationStatus.PENDING.value, NotificationStatus.SENDING.value]
            ),
        )
        .values(
            status=NotificationStatus.CANCELLED.value,
            last_error="账户已恢复正常，取消发送",
        )
    )
    session.commit()
    logger.info("已恢复正常，关闭异常事件 %s 个", len(alerts))
    return len(alerts)


def _last_checkin_subquery():
    return (
        select(
            CheckinRecord.account_id.label("account_id"),
            func.max(CheckinRecord.checked_in_at).label("last_at"),
        )
        .group_by(CheckinRecord.account_id)
        .subquery()
    )


def scan_once(
    session: Session,
    *,
    now: datetime | None = None,
    limit: int | None = None,
) -> ScanStats:
    """扫描到期账户，创建异常事件与通知任务。

    幂等保证：
    - 同一账户同一 ``due_at`` 只有一条 ``safety_alert``（唯一约束 + savepoint 兜底）
    - 该账户已存在未处理事件时不再重复创建
    - 通知任务以 ``dedupe_key`` 唯一约束去重

    分批方式：按 ``Account.id`` 做键集分页，保证账户数超过单批上限时
    不会永远只扫描到前 ``batch`` 个账户。
    """
    current = ensure_utc(now or now_utc())
    batch = max(int(limit or settings.SCHEDULER_BATCH_SIZE), 1)
    stats = ScanStats()

    last_subq = _last_checkin_subquery()
    base_stmt = (
        select(Account, CheckinSetting, last_subq.c.last_at)
        .join(CheckinSetting, CheckinSetting.account_id == Account.id)
        .outerjoin(last_subq, last_subq.c.account_id == Account.id)
        .where(Account.status == AccountStatus.ACTIVE.value)
        .order_by(Account.id)
    )

    # account.id 为 UUIDv7（时间有序），键集分页用「上一批最后一个 id」，
    # 首批不加条件（不能用 0 这类整数哨兵，UUID 与整数无法比较）
    cursor: uuid.UUID | None = None
    while True:
        stmt = base_stmt if cursor is None else base_stmt.where(Account.id > cursor)
        rows = session.execute(stmt.limit(batch)).all()
        if not rows:
            break
        for account, setting, last_at in rows:
            stats.scanned += 1
            try:
                _process_account(session, account, setting, last_at, current, stats)
            except Exception as exc:  # noqa: BLE001 - 单个账户失败不影响整体扫描
                session.rollback()
                message = f"account={account.public_id} {type(exc).__name__}: {exc}"
                stats.errors.append(message)
                logger.exception("扫描账户失败 %s", account.public_id)
        cursor = rows[-1][0].id  # type: ignore[assignment]
        if len(rows) < batch:
            break

    return stats


def _process_account(
    session: Session,
    account: Account,
    setting: CheckinSetting,
    last_at: datetime | None,
    now: datetime,
    stats: ScanStats,
) -> None:
    anchor = last_at or account.created_at
    state = compute_schedule(
        anchor_at=anchor,
        period_days=setting.period_days,
        checkin_time_local=setting.checkin_time_local,
        timezone=setting.timezone,
        reminder_offsets=setting.reminder_offsets_safe(),
        alert_offset_minutes=setting.alert_offset_minutes,
        now=now,
        reminders_enabled=setting.reminders_enabled,
    )
    if not state.alert_due:
        return

    open_alert = session.exec(
        select(SafetyAlert).where(
            SafetyAlert.account_id == account.id,
            SafetyAlert.status == SafetyAlertStatus.OPEN.value,
        )
    ).first()
    if open_alert is not None:
        stats.alerts_existing += 1
        return

    guardians = list(
        session.exec(
            select(Guardian)
            .where(Guardian.account_id == account.id)
            .order_by(Guardian.sort_order, Guardian.id)  # type: ignore[attr-defined]
        ).all()
    )

    alert = SafetyAlert(
        account_id=account.id,
        due_at=state.due_at,
        triggered_at=now,
        status=SafetyAlertStatus.OPEN.value,
        overdue_minutes=int((now - state.due_at).total_seconds() // 60),
        guardian_count=len(guardians),
        notified_guardian_count=0,
    )
    try:
        with session.begin_nested():
            session.add(alert)
            session.flush()
    except IntegrityError:
        stats.alerts_existing += 1
        logger.info("异常事件已存在（唯一约束命中） account_id=%s", account.public_id)
        return

    stats.alerts_created += 1
    created = create_alert_notifications(
        session, alert, account, setting, guardians, now, last_checkin_at=last_at
    )
    stats.notifications_created += created
    if not guardians:
        stats.skipped_no_guardian += 1
    alert.notified_guardian_count = created
    session.add(alert)
    session.commit()
    logger.info(
        "创建异常事件 account_id=%s due_at=%s guardians=%s notifications=%s",
        account.public_id,
        state.due_at.isoformat(),
        len(guardians),
        created,
    )


def create_alert_notifications(
    session: Session,
    alert: SafetyAlert,
    account: Account,
    setting: CheckinSetting,
    guardians: list[Guardian],
    now: datetime,
    *,
    last_checkin_at: datetime | None = None,
) -> int:
    """为异常事件生成邮件任务（与发送解耦）。"""
    created = 0
    for guardian in guardians:
        dedupe_key = f"alert:{alert.id}:guardian:{guardian.id}:email"
        ctx = AlertEmailContext(
            guardian_name=guardian.name,
            period_days=setting.period_days,
            last_checkin_at=last_checkin_at,
            due_at=alert.due_at,
            triggered_at=alert.triggered_at,
            overdue_hours=max(alert.overdue_minutes // 60, 1),
            timezone=setting.timezone,
        )
        subject, text, html = render_alert_email(ctx)
        record = NotificationRecord(
            alert_id=alert.id,
            account_id=account.id,
            guardian_id=guardian.id,
            channel="email",
            kind="alert",
            recipient_email=guardian.email,
            recipient_name=guardian.name,
            subject=subject,
            dedupe_key=dedupe_key,
            status=NotificationStatus.PENDING.value,
            attempts=0,
            max_attempts=settings.EMAIL_MAX_ATTEMPTS,
            next_attempt_at=now,
            # 供发送时渲染正文
            last_error=None,
        )
        try:
            with session.begin_nested():
                session.add(record)
                session.flush()
            created += 1
        except IntegrityError:
            logger.info("通知任务已存在，跳过 dedupe_key=%s", dedupe_key)
    return created


def build_alert_email_context(
    session: Session,
    record: NotificationRecord,
    alert: SafetyAlert,
) -> AlertEmailContext:
    setting = session.exec(
        select(CheckinSetting).where(CheckinSetting.account_id == record.account_id)
    ).first()
    last_at = session.exec(
        select(func.max(CheckinRecord.checked_in_at)).where(
            CheckinRecord.account_id == record.account_id
        )
    ).one()
    return AlertEmailContext(
        guardian_name=record.recipient_name,
        period_days=setting.period_days if setting else 1,
        last_checkin_at=last_at,
        due_at=alert.due_at,
        triggered_at=alert.triggered_at,
        overdue_hours=max(alert.overdue_minutes // 60, 1),
        timezone=setting.timezone if setting else settings.DEFAULT_TIMEZONE,
    )
