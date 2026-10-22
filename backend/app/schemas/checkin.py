"""确认设置、状态与历史 DTO。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.models.enums import CheckinStage
from app.schemas.base import CamelModel
from app.services.timeutil import is_valid_hhmm, is_valid_tz


class ReminderSlotRead(CamelModel):
    index: int
    offset_minutes: int
    at: datetime
    local_at: str
    passed: bool
    label: str


class CheckinSettingRead(CamelModel):
    period_days: int
    checkin_time: str
    timezone: str
    reminders_enabled: bool
    alert_offset_minutes: int
    reminders: list[ReminderSlotRead]
    updated_at: datetime


class CheckinSettingUpdate(CamelModel):
    period_days: int | None = Field(default=None, ge=1, le=30)
    checkin_time: str | None = Field(default=None, max_length=5)
    timezone: str | None = Field(default=None, max_length=64)
    reminders_enabled: bool | None = None

    @field_validator("checkin_time")
    @classmethod
    def _validate_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not is_valid_hhmm(value):
            raise ValueError("确认时间格式必须为 HH:MM（24 小时制）")
        return value.strip()

    @field_validator("timezone")
    @classmethod
    def _validate_tz(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not is_valid_tz(value):
            raise ValueError("无效的时区标识")
        return value.strip()


class OpenAlertRead(CamelModel):
    id: int
    due_at: datetime
    triggered_at: datetime
    overdue_minutes: int
    guardian_count: int


class CheckinStatusRead(CamelModel):
    """首页状态：所有时间均由服务端计算，客户端时间不参与判断。"""

    stage: CheckinStage
    server_time: datetime
    timezone: str
    period_days: int
    checkin_time: str
    last_checkin_at: datetime | None
    next_checkin_at: datetime | None
    alert_at: datetime | None
    seconds_until_due: int
    overdue_seconds: int
    next_reminder_at: datetime | None
    reminders_passed: int
    reminders: list[ReminderSlotRead]
    progress_ratio: float
    guardian_count: int
    has_open_alert: bool
    open_alert: OpenAlertRead | None = None
    stage_hint: str


class CheckinCreateRequest(CamelModel):
    request_id: str = Field(min_length=8, max_length=64, description="幂等键，重复提交返回同一条记录")
    client_time: datetime | None = None
    note: str | None = Field(default=None, max_length=200)


class CheckinRecordRead(CamelModel):
    id: int
    checked_in_at: datetime
    client_time: datetime | None
    due_at: datetime | None
    source: str
    note: str | None


class CheckinCreateResponse(CamelModel):
    record: CheckinRecordRead
    duplicated: bool
    resolved_alert: bool
    status: CheckinStatusRead


class CheckinHistoryResponse(CamelModel):
    items: list[CheckinRecordRead]
    next_cursor: str | None
    has_more: bool
