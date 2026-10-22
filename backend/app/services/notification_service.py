"""通知任务派发：发送、重试、去重、故障恢复。

设计要点
--------
- 任务与发送解耦：异常事件只负责生成 ``notification_record``，本模块负责真正发信
- 先置为 SENDING 再发信：进程崩溃后可由 ``recover_stale`` 重新纳入队列
- 失败按 ``EMAIL_RETRY_BACKOFF_SECONDS * attempts`` 退避重试，超过上限置 FAILED
- 事件已恢复（resolved）时，剩余任务直接置 CANCELLED，不再打扰守护人
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.core.config import settings
from app.core.logging import get_logger
from app.models import NotificationRecord, SafetyAlert
from app.models.enums import NotificationStatus, SafetyAlertStatus
from app.services.alert_service import build_alert_email_context
from app.services.mail import (
    EmailNotConfigured,
    OutgoingEmail,
    get_sender,
    render_alert_email,
)
from app.services.timeutil import ensure_utc, now_utc

logger = get_logger(__name__)

STALE_SENDING_SECONDS = 600


@dataclass
class DispatchStats:
    picked: int = 0
    sent: int = 0
    simulated: int = 0
    failed: int = 0
    retry_scheduled: int = 0
    cancelled: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "picked": self.picked,
            "sent": self.sent,
            "simulated": self.simulated,
            "failed": self.failed,
            "retryScheduled": self.retry_scheduled,
            "cancelled": self.cancelled,
            "errors": self.errors,
        }


def recover_stale(session: Session, *, now: datetime | None = None) -> int:
    """把卡在 SENDING 的任务（进程崩溃/重启）放回队列。"""
    current = ensure_utc(now or now_utc())
    threshold = current - timedelta(seconds=STALE_SENDING_SECONDS)
    stale = list(
        session.exec(
            select(NotificationRecord).where(
                NotificationRecord.status == NotificationStatus.SENDING.value,
                NotificationRecord.last_attempt_at.is_not(None),  # type: ignore[union-attr]
                NotificationRecord.last_attempt_at < threshold,  # type: ignore[operator]
            )
        ).all()
    )
    for record in stale:
        record.status = NotificationStatus.PENDING.value
        record.last_error = "上次发送中断，已自动重新入队"
        session.add(record)
    if stale:
        session.commit()
        logger.warning("恢复 %s 条中断的通知任务", len(stale))
    return len(stale)


def dispatch_pending(
    session: Session,
    *,
    now: datetime | None = None,
    limit: int | None = None,
) -> DispatchStats:
    current = ensure_utc(now or now_utc())
    batch = limit or settings.SCHEDULER_BATCH_SIZE
    stats = DispatchStats()

    recover_stale(session, now=current)

    rows = list(
        session.exec(
            select(NotificationRecord)
            .where(
                NotificationRecord.status == NotificationStatus.PENDING.value,
                NotificationRecord.next_attempt_at <= current,
            )
            .order_by(NotificationRecord.next_attempt_at, NotificationRecord.id)  # type: ignore[attr-defined]
            .limit(batch)
        ).all()
    )
    stats.picked = len(rows)

    for record in rows:
        try:
            _dispatch_one(session, record, current, stats)
        except Exception as exc:  # noqa: BLE001 - 单条失败不影响其余
            session.rollback()
            stats.failed += 1
            stats.errors.append(f"notification={record.id} {type(exc).__name__}: {exc}")
            logger.exception("通知派发异常 notification_id=%s", record.id)

    return stats


def _dispatch_one(
    session: Session,
    record: NotificationRecord,
    now: datetime,
    stats: DispatchStats,
) -> None:
    alert = session.get(SafetyAlert, record.alert_id)
    if alert is None or alert.status != SafetyAlertStatus.OPEN.value:
        record.status = NotificationStatus.CANCELLED.value
        record.last_error = "异常事件已恢复，取消发送"
        session.add(record)
        session.commit()
        stats.cancelled += 1
        return

    # 占用任务（先落库，防止并发/重启导致重复发送）
    record.status = NotificationStatus.SENDING.value
    record.last_attempt_at = now
    record.attempts += 1
    session.add(record)
    session.commit()
    session.refresh(record)

    try:
        sender = get_sender()
    except EmailNotConfigured as exc:
        _mark_failed(
            session, record, now, f"邮件服务未正确配置：{exc}", stats, permanent=True
        )
        logger.error("邮件未配置，任务失败 notification_id=%s", record.id)
        return

    ctx = build_alert_email_context(session, record, alert)
    subject, text, html = render_alert_email(ctx)
    message = OutgoingEmail(
        to_email=record.recipient_email,
        to_name=record.recipient_name,
        subject=subject,
        text_body=text,
        html_body=html,
    )

    result = sender.send(message)
    if result.ok:
        record.status = NotificationStatus.SENT.value
        record.sent_at = now
        record.simulated = bool(result.simulated)
        record.last_error = None
        session.add(record)
        session.commit()
        stats.sent += 1
        if result.simulated:
            stats.simulated += 1
        logger.info(
            "通知发送成功 notification_id=%s simulated=%s", record.id, result.simulated
        )
        return

    _mark_failed(session, record, now, result.error or "未知错误", stats)


def _mark_failed(
    session: Session,
    record: NotificationRecord,
    now: datetime,
    error: str,
    stats: DispatchStats,
    *,
    permanent: bool = False,
) -> None:
    record.last_error = error[:500]
    if permanent or record.attempts >= record.max_attempts:
        record.status = NotificationStatus.FAILED.value
        stats.failed += 1
        logger.warning(
            "通知最终失败 notification_id=%s attempts=%s err=%s",
            record.id,
            record.attempts,
            error,
        )
    else:
        backoff = settings.EMAIL_RETRY_BACKOFF_SECONDS * record.attempts
        record.status = NotificationStatus.PENDING.value
        record.next_attempt_at = now + timedelta(seconds=backoff)
        stats.retry_scheduled += 1
        logger.info(
            "通知发送失败，%s 秒后重试 notification_id=%s attempts=%s",
            backoff,
            record.id,
            record.attempts,
        )
    session.add(record)
    session.commit()
