"""时间、时区与格式化工具。

约束：服务端一律以 UTC 存储与比较时间；只有在「计算本地确认时间点」时才转换到用户时区。
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.base import utcnow

_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def now_utc() -> datetime:
    return utcnow()


def resolve_tz(name: str | None) -> ZoneInfo:
    """解析 IANA 时区；非法时区抛出 ValueError。"""
    candidate = (name or "Asia/Shanghai").strip()
    try:
        return ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"无效的时区：{candidate}") from exc


def is_valid_tz(name: str | None) -> bool:
    try:
        resolve_tz(name)
        return True
    except ValueError:
        return False


def parse_hhmm(value: str) -> tuple[int, int]:
    match = _HHMM_RE.match((value or "").strip())
    if not match:
        raise ValueError("时间格式必须为 HH:MM（24 小时制）")
    return int(match.group(1)), int(match.group(2))


def is_valid_hhmm(value: str) -> bool:
    return bool(_HHMM_RE.match((value or "").strip()))


def local_time_to_utc(local_date: date, hh: int, mm: int, tz: ZoneInfo) -> datetime:
    """把「用户时区的某天某时刻」转换为 UTC。

    夏令时缺失的时刻：zoneinfo 会给出一个必然等于某个真实时刻的解释，
    这里再做一次向上取整，避免出现「本地时间不存在导致永远触发不了」。
    """
    naive = datetime.combine(local_date, time(hour=hh, minute=mm))
    aware = naive.replace(tzinfo=tz)
    utc_value = aware.astimezone(UTC)
    roundtrip = utc_value.astimezone(tz)
    if roundtrip.replace(tzinfo=None) != naive:
        # 该本地时刻在当天不存在（夏令时跳变），顺延到跳变后的第一个有效时刻
        aware = roundtrip.replace(tzinfo=tz) + (naive - roundtrip.replace(tzinfo=None))
        utc_value = aware.astimezone(UTC)
    return utc_value


def to_local(value: datetime, tz: ZoneInfo) -> datetime:
    return ensure_utc(value).astimezone(tz)  # type: ignore[union-attr]


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return ensure_utc(value).isoformat().replace("+00:00", "Z")  # type: ignore[union-attr]


def iso_local(value: datetime | None, tz: ZoneInfo) -> str | None:
    if value is None:
        return None
    return to_local(value, tz).isoformat()


def humanize_remaining(seconds: int) -> str:
    """把剩余秒数转换为中文可读文案。"""
    if seconds <= 0:
        return "已超时"
    minutes = seconds // 60
    if minutes < 60:
        return f"{max(minutes, 1)} 分钟后"
    hours, mins = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} 小时 {mins} 分钟后" if mins else f"{hours} 小时后"
    days, hours = divmod(hours, 24)
    return f"{days} 天 {hours} 小时后" if hours else f"{days} 天后"


def humanize_ago(value: datetime | None, *, now: datetime | None = None, tz: ZoneInfo | None = None) -> str:
    """相对时间文案（用于前端展示兜底）。"""
    if value is None:
        return "从未确认"
    delta = (now or utcnow()) - ensure_utc(value)  # type: ignore[operator]
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"{seconds // 60} 分钟前"
    if seconds < 86400:
        return f"{seconds // 3600} 小时前"
    return f"{seconds // 86400} 天前"


def add_minutes(value: datetime, minutes: int) -> datetime:
    return ensure_utc(value) + timedelta(minutes=minutes)  # type: ignore[operator]
