"""确认周期的纯计算逻辑（无数据库依赖，便于单元测试）。

时间语义
--------
- ``anchor_at``：上一次确认时间（首次使用为账户创建时间），UTC
- ``due_at``：本次应确认时间 = anchor 所在本地日期 + period_days 天的本地 time 点，转为 UTC
- ``alert_at``：due_at + alert_offset_minutes（默认 1440 分钟 = 次日同一时刻）
- 提醒偏移：相对应确认时间的分钟数，默认 [30, 240, 720] → 08:30 / 12:00 / 20:00

阶段划分
--------
- ``NORMAL``   now < due_at
- ``PENDING``  due_at <= now < 第一次提醒
- ``REMINDING`` 第一次提醒 <= now < alert_at
- ``ALERT``    now >= alert_at
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.enums import CheckinStage
from app.services.timeutil import (
    add_minutes,
    ensure_utc,
    local_time_to_utc,
    parse_hhmm,
    resolve_tz,
    to_local,
)


@dataclass(frozen=True)
class ReminderSlot:
    index: int
    offset_minutes: int
    at: datetime
    passed: bool


@dataclass(frozen=True)
class ScheduleState:
    stage: CheckinStage
    anchor_at: datetime
    due_at: datetime
    alert_at: datetime
    reminders: tuple[ReminderSlot, ...]
    next_reminder_at: datetime | None
    reminders_passed: int
    seconds_until_due: int
    overdue_seconds: int
    alert_due: bool
    progress_ratio: float

    @property
    def is_overdue(self) -> bool:
        return self.overdue_seconds > 0


def compute_due_at(
    anchor_at: datetime,
    period_days: int,
    checkin_time_local: str,
    timezone: str,
) -> datetime:
    """计算应确认时间（UTC）。"""
    if period_days < 1:
        raise ValueError("确认周期至少为 1 天")
    tz = resolve_tz(timezone)
    hour, minute = parse_hhmm(checkin_time_local)
    anchor_local = to_local(anchor_at, tz)
    target_date = anchor_local.date() + timedelta(days=period_days)
    return local_time_to_utc(target_date, hour, minute, tz)


def compute_schedule(
    *,
    anchor_at: datetime,
    period_days: int,
    checkin_time_local: str,
    timezone: str,
    reminder_offsets: list[int],
    alert_offset_minutes: int,
    now: datetime,
    reminders_enabled: bool = True,
) -> ScheduleState:
    anchor = ensure_utc(anchor_at)  # type: ignore[assignment]
    current = ensure_utc(now)  # type: ignore[assignment]
    due_at = compute_due_at(anchor, period_days, checkin_time_local, timezone)
    alert_at = add_minutes(due_at, alert_offset_minutes)

    offsets = sorted({int(item) for item in reminder_offsets if int(item) > 0})
    if not reminders_enabled:
        offsets = []

    slots: list[ReminderSlot] = []
    for idx, offset in enumerate(offsets, start=1):
        at = add_minutes(due_at, offset)
        slots.append(ReminderSlot(index=idx, offset_minutes=offset, at=at, passed=current >= at))

    first_reminder_at = slots[0].at if slots else alert_at
    if current < due_at:
        stage = CheckinStage.NORMAL
    elif current < first_reminder_at:
        stage = CheckinStage.PENDING
    elif current < alert_at:
        stage = CheckinStage.REMINDING
    else:
        stage = CheckinStage.ALERT

    next_reminder = next((slot.at for slot in slots if not slot.passed), None)
    if stage == CheckinStage.ALERT:
        next_reminder = None

    window_seconds = max(int((alert_at - due_at).total_seconds()), 1)
    elapsed = int((current - due_at).total_seconds())
    progress = min(max(elapsed / window_seconds, 0.0), 1.0)

    return ScheduleState(
        stage=stage,
        anchor_at=anchor,
        due_at=due_at,
        alert_at=alert_at,
        reminders=tuple(slots),
        next_reminder_at=next_reminder,
        reminders_passed=sum(1 for slot in slots if slot.passed),
        seconds_until_due=max(int((due_at - current).total_seconds()), 0),
        overdue_seconds=max(elapsed, 0),
        alert_due=current >= alert_at,
        progress_ratio=round(progress, 4),
    )


def next_due_after_checkin(
    checked_in_at: datetime,
    period_days: int,
    checkin_time_local: str,
    timezone: str,
) -> datetime:
    """确认成功后新的应确认时间。"""
    return compute_due_at(checked_in_at, period_days, checkin_time_local, timezone)
