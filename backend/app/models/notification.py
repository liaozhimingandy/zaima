"""异常事件与邮件通知记录。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, ForeignKey, Index, Integer, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin, UTCDateTime, utcnow
from app.models.enums import (
    NotificationChannel,
    NotificationKind,
    NotificationStatus,
    SafetyAlertStatus,
)


class SafetyAlert(TimestampMixin, SQLModel, table=True):
    """长时间未确认事件。

    注意：该事件仅代表「长时间未确认」，不代表发生事故或死亡。
    以 (account_id, due_at) 唯一约束保证同一确认窗口只产生一个事件。
    """

    __tablename__ = "safety_alert"
    __table_args__ = (
        UniqueConstraint("account_id", "due_at", name="uq_alert_account_due"),
        Index("ix_alert_status_triggered", "status", "triggered_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True, nullable=False)
    # 触发该事件的应确认时间
    due_at: datetime = Field(sa_type=UTCDateTime, nullable=False)
    triggered_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime, nullable=False)
    status: str = Field(default=SafetyAlertStatus.OPEN.value, max_length=16, nullable=False)
    resolved_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    resolved_by: str | None = Field(default=None, max_length=32)
    # 触发时已超时的分钟数，便于事后回溯
    overdue_minutes: int = Field(default=0, nullable=False)
    # 触发时已配置的守护人快照数量
    guardian_count: int = Field(default=0, nullable=False)
    notified_guardian_count: int = Field(default=0, nullable=False)


class NotificationRecord(TimestampMixin, SQLModel, table=True):
    """一次通知任务（当前仅邮件）。

    ``dedupe_key`` 唯一约束保证同一事件、同一守护人、同一类型只生成一条任务。
    """

    __tablename__ = "notification_record"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_notification_dedupe"),
        Index("ix_notification_status_next", "status", "next_attempt_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    alert_id: int = Field(foreign_key="safety_alert.id", index=True, nullable=False)
    account_id: int = Field(foreign_key="account.id", index=True, nullable=False)
    guardian_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("guardian.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    channel: str = Field(default=NotificationChannel.EMAIL.value, max_length=16, nullable=False)
    kind: str = Field(default=NotificationKind.ALERT.value, max_length=16, nullable=False)
    # 收件邮箱快照：即使守护人被删除，历史仍可追溯
    recipient_email: str = Field(max_length=254, nullable=False)
    recipient_name: str = Field(default="", max_length=32, nullable=False)
    subject: str = Field(default="", max_length=200, nullable=False)
    dedupe_key: str = Field(max_length=128, nullable=False)

    status: str = Field(default=NotificationStatus.PENDING.value, max_length=16, nullable=False)
    attempts: int = Field(default=0, nullable=False)
    max_attempts: int = Field(default=3, nullable=False)
    next_attempt_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime, nullable=False)
    last_attempt_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    sent_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    last_error: str | None = Field(default=None, max_length=500)
    # 是否为模拟发送（开发环境），便于区分真实结果
    simulated: bool = Field(default=False, nullable=False)
