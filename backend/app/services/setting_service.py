"""确认设置服务。"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.core.config import settings as app_settings
from app.core.errors import ValidationError
from app.models import Account, CheckinSetting
from app.schemas.checkin import CheckinSettingRead, CheckinSettingUpdate, ReminderSlotRead
from app.services.schedule import compute_due_at
from app.services.timeutil import add_minutes, iso_local, resolve_tz

REMINDER_LABELS = ["第一次提醒", "第二次提醒", "第三次提醒", "第四次提醒", "第五次提醒"]


def ensure_setting(
    session: Session,
    account: Account,
    *,
    timezone: str | None = None,
) -> CheckinSetting:
    existing = session.exec(
        select(CheckinSetting).where(CheckinSetting.account_id == account.id)
    ).first()
    if existing is not None:
        return existing

    setting = CheckinSetting(
        account_id=account.id,
        period_days=app_settings.DEFAULT_PERIOD_DAYS,
        checkin_time_local=app_settings.DEFAULT_CHECKIN_TIME,
        timezone=timezone or app_settings.DEFAULT_TIMEZONE,
        reminder_offsets=app_settings.reminder_offsets,
        alert_offset_minutes=app_settings.ALERT_OFFSET_MINUTES,
        reminders_enabled=True,
    )
    session.add(setting)
    session.commit()
    session.refresh(setting)
    return setting


def get_setting(session: Session, account: Account) -> CheckinSetting:
    return ensure_setting(session, account)


def update_setting(
    session: Session,
    account: Account,
    payload: CheckinSettingUpdate,
) -> CheckinSetting:
    setting = get_setting(session, account)

    if payload.period_days is not None:
        if payload.period_days not in app_settings.allowed_period_days:
            allowed = "、".join(str(item) for item in app_settings.allowed_period_days)
            raise ValidationError(f"确认周期仅支持：{allowed} 天")
        setting.period_days = payload.period_days
    if payload.checkin_time is not None:
        setting.checkin_time_local = payload.checkin_time
    if payload.timezone is not None:
        setting.timezone = payload.timezone
    if payload.reminders_enabled is not None:
        setting.reminders_enabled = payload.reminders_enabled

    session.add(setting)
    session.commit()
    session.refresh(setting)
    return setting


def build_setting_read(
    setting: CheckinSetting,
    anchor_at: datetime,
) -> CheckinSettingRead:
    tz = resolve_tz(setting.timezone)
    due_at = compute_due_at(
        anchor_at, setting.period_days, setting.checkin_time_local, setting.timezone
    )
    reminders: list[ReminderSlotRead] = []
    for index, offset in enumerate(setting.reminder_offsets_safe(), start=1):
        at = add_minutes(due_at, offset)
        reminders.append(
            ReminderSlotRead(
                index=index,
                offset_minutes=offset,
                at=at,
                local_at=iso_local(at, tz) or "",
                passed=False,
                label=(
                    REMINDER_LABELS[index - 1]
                    if index - 1 < len(REMINDER_LABELS)
                    else f"第 {index} 次提醒"
                ),
            )
        )
    return CheckinSettingRead(
        period_days=setting.period_days,
        checkin_time=setting.checkin_time_local,
        timezone=setting.timezone,
        reminders_enabled=setting.reminders_enabled,
        alert_offset_minutes=setting.alert_offset_minutes,
        reminders=reminders,
        updated_at=setting.updated_at,
    )
