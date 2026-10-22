"""公共字段与通用类型。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, TypeDecorator
from sqlmodel import Field


def utcnow() -> datetime:
    """当前 UTC 时间（带时区）。服务端统一使用 UTC 存储。"""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """跨数据库的 UTC 时间列。

    - PostgreSQL：timestamptz，存取均为 aware UTC
    - SQLite（测试）：以 naive UTC 存取，读取时补回 UTC 时区
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        value = value.astimezone(UTC)
        if dialect.name == "sqlite":
            return value.replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class TimestampMixin:
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime, nullable=False)
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_type=UTCDateTime,
        nullable=False,
        sa_column_kwargs={"onupdate": utcnow},
    )
