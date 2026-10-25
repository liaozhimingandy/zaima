"""确认设置与确认记录。"""

from __future__ import annotations

import uuid

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import UTCDateTime, created_at_column, updated_at_column
from app.models.enums import CheckinSource


class CheckinSetting(SQLModel, table=True):
    """每个账户唯一的确认周期与提醒设置。"""

    __tablename__ = "checkin_setting"
    __table_args__ = (UniqueConstraint("account_id", name="uq_setting_account"),)

    id: int | None = Field(default=None, primary_key=True)
    account_id: uuid.UUID = Field(foreign_key="account.id", index=True, nullable=False)
    period_days: int = Field(default=1, ge=1, le=30, nullable=False)
    # 本地确认时间点，HH:MM
    checkin_time_local: str = Field(default="08:00", max_length=5, nullable=False)
    # IANA 时区，例如 Asia/Shanghai
    timezone: str = Field(default="Asia/Shanghai", max_length=64, nullable=False)
    # 相对应确认时间的提醒偏移（分钟），升序
    reminder_offsets: list[int] = Field(
        default_factory=lambda: [30, 240, 720],
        sa_column=Column(JSON, nullable=False),
    )
    # 触发异常事件的偏移（分钟）
    alert_offset_minutes: int = Field(default=1440, ge=1, nullable=False)
    reminders_enabled: bool = Field(default=True, nullable=False)

    # 时间字段置于表末
    created_at: datetime = created_at_column()
    updated_at: datetime = updated_at_column()

    def reminder_offsets_safe(self) -> list[int]:
        value: Any = self.reminder_offsets
        if not isinstance(value, list):
            return [30, 240, 720]
        return sorted(int(item) for item in value)


class CheckinRecord(SQLModel, table=True):
    """一次「我在」确认。"""

    __tablename__ = "checkin_record"
    __table_args__ = (
        UniqueConstraint("account_id", "idempotency_key", name="uq_checkin_account_key"),
        Index("ix_checkin_account_time", "account_id", "checked_in_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    account_id: uuid.UUID = Field(foreign_key="account.id", index=True, nullable=False)
    # 服务端确认时间（UTC），一切判断以此为准
    checked_in_at: datetime = Field(sa_type=UTCDateTime, nullable=False, index=True)
    # 客户端上报时间，仅作展示参考，不参与业务判定
    client_time: datetime | None = Field(default=None, sa_type=UTCDateTime)
    # 本次确认所解除的应确认时间（未到期确认时也记录窗口锚点）
    due_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    idempotency_key: str = Field(max_length=64, nullable=False)
    source: str = Field(default=CheckinSource.MANUAL.value, max_length=16, nullable=False)
    note: str | None = Field(default=None, max_length=200)

    # 时间字段置于表末
    created_at: datetime = created_at_column()
    updated_at: datetime = updated_at_column()
