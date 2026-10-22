"""确认周期与状态机的纯函数测试（不依赖数据库）。"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.models.enums import CheckinStage
from app.services.schedule import compute_due_at, compute_schedule


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def schedule(**overrides):
    base = dict(
        anchor_at=dt("2026-02-28T12:00:00"),
        period_days=1,
        checkin_time_local="08:00",
        timezone="Asia/Shanghai",
        reminder_offsets=[30, 240, 720],
        alert_offset_minutes=1440,
        now=dt("2026-03-01T00:00:00"),
        reminders_enabled=True,
    )
    base.update(overrides)
    return compute_schedule(**base)


def test_due_is_next_local_0800():
    # 上海时间 2026-03-01 08:00 = 2026-03-01T00:00Z
    anchor = dt("2026-02-28T12:00:00")  # 上海 20:00
    due = compute_due_at(anchor, 1, "08:00", "Asia/Shanghai")
    assert due == dt("2026-03-01T00:00:00")


def test_due_honours_period_days():
    anchor = dt("2026-03-01T00:00:00")  # 上海 08:00
    assert compute_due_at(anchor, 1, "08:00", "Asia/Shanghai") == dt("2026-03-02T00:00:00")
    assert compute_due_at(anchor, 2, "08:00", "Asia/Shanghai") == dt("2026-03-03T00:00:00")
    assert compute_due_at(anchor, 3, "08:00", "Asia/Shanghai") == dt("2026-03-04T00:00:00")
    assert compute_due_at(anchor, 7, "08:00", "Asia/Shanghai") == dt("2026-03-08T00:00:00")


def test_stage_progression_matches_default_rules():
    kwargs = dict(anchor_at=dt("2026-02-28T12:00:00"))
    # 07:59 本地 —— 未到期
    assert schedule(now=dt("2026-02-28T23:59:00"), **kwargs).stage == CheckinStage.NORMAL
    # 08:00 本地 —— 已到期，宽限期
    assert schedule(now=dt("2026-03-01T00:00:00"), **kwargs).stage == CheckinStage.PENDING
    # 08:29 —— 仍在宽限期
    assert schedule(now=dt("2026-03-01T00:29:00"), **kwargs).stage == CheckinStage.PENDING
    # 08:30 —— 第一次提醒
    state = schedule(now=dt("2026-03-01T00:30:00"), **kwargs)
    assert state.stage == CheckinStage.REMINDING
    assert state.reminders_passed == 1
    # 12:00 —— 第二次提醒
    assert schedule(now=dt("2026-03-01T04:00:00"), **kwargs).reminders_passed == 2
    # 20:00 —— 第三次提醒
    assert schedule(now=dt("2026-03-01T12:00:00"), **kwargs).reminders_passed == 3
    # 20:01 —— 提醒全部走完但未触发异常
    late = schedule(now=dt("2026-03-01T12:01:00"), **kwargs)
    assert late.stage == CheckinStage.REMINDING
    assert late.next_reminder_at is None
    # 次日 08:00 —— 触发异常
    assert schedule(now=dt("2026-03-02T00:00:00"), **kwargs).stage == CheckinStage.ALERT


def test_alert_flag_only_after_offset():
    kwargs = dict(anchor_at=dt("2026-02-28T12:00:00"))
    assert schedule(now=dt("2026-03-01T23:59:00"), **kwargs).alert_due is False
    assert schedule(now=dt("2026-03-02T00:00:01"), **kwargs).alert_due is True


def test_next_reminder_at_tracks_slots():
    state = schedule(now=dt("2026-02-28T12:00:00"), anchor_at=dt("2026-02-28T12:00:00"))
    assert state.next_reminder_at == dt("2026-03-01T00:30:00")
    state2 = schedule(now=dt("2026-03-01T04:30:00"), anchor_at=dt("2026-02-28T12:00:00"))
    assert state2.next_reminder_at == dt("2026-03-01T12:00:00")


def test_reminders_can_be_disabled():
    state = schedule(
        now=dt("2026-03-01T04:00:00"),
        anchor_at=dt("2026-02-28T12:00:00"),
        reminders_enabled=False,
    )
    # 关闭提醒后：到期后一直处于 PENDING，直到异常阈值（不出现 REMINDING）
    assert state.stage == CheckinStage.PENDING
    assert state.reminders == ()
    assert state.reminders_passed == 0


def test_dst_spring_forward_uses_real_local_time():
    """美东 2026-03-08 进入夏令时：本地 08:00 应是 UTC-4 的 12:00Z。"""
    anchor = datetime(2026, 3, 7, 20, 0, tzinfo=UTC)  # 本地 15:00 EST
    due = compute_due_at(anchor, 1, "08:00", "America/New_York")
    local = due.astimezone(ZoneInfo("America/New_York"))
    assert (local.hour, local.minute) == (8, 0)
    assert due.hour == 12  # EDT = UTC-4


def test_dst_fall_back_keeps_local_time():
    anchor = datetime(2026, 10, 31, 20, 0, tzinfo=UTC)
    due = compute_due_at(anchor, 1, "08:00", "America/New_York")
    local = due.astimezone(ZoneInfo("America/New_York"))
    assert (local.hour, local.minute) == (8, 0)
    assert due.hour == 13  # EST = UTC-5


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        compute_due_at(dt("2026-03-01T00:00:00"), 0, "08:00", "Asia/Shanghai")
    with pytest.raises(ValueError):
        compute_due_at(dt("2026-03-01T00:00:00"), 1, "25:00", "Asia/Shanghai")
    with pytest.raises(ValueError):
        compute_due_at(dt("2026-03-01T00:00:00"), 1, "08:00", "Not/AZone")


def test_progress_ratio_is_bounded():
    state = schedule(now=dt("2026-03-02T12:00:00"), anchor_at=dt("2026-02-28T12:00:00"))
    assert state.progress_ratio == 1.0
    state2 = schedule(now=dt("2026-02-28T12:00:00"), anchor_at=dt("2026-02-28T12:00:00"))
    assert state2.progress_ratio == 0.0
