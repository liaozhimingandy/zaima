"""领域枚举值。数据库中以字符串存储，避免依赖数据库原生 ENUM。"""

from __future__ import annotations

from enum import StrEnum


class AccountStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class CheckinSource(StrEnum):
    MANUAL = "manual"


class GuardianRelation(StrEnum):
    FAMILY = "family"
    FRIEND = "friend"
    PARTNER = "partner"
    COLLEAGUE = "colleague"
    OTHER = "other"


class SafetyAlertStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class NotificationChannel(StrEnum):
    EMAIL = "email"


class NotificationKind(StrEnum):
    ALERT = "alert"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"  # 账户已恢复，取消后续发送


class CheckinStage(StrEnum):
    """首页展示的提醒阶段（由服务端根据时间计算，客户端不可信）。"""

    NORMAL = "NORMAL"  # 未到期
    PENDING = "PENDING"  # 已到期，处于宽限期（首次提醒前）
    REMINDING = "REMINDING"  # 提醒阶段（第 1~3 次提醒）
    ALERT = "ALERT"  # 已触发异常事件（长时间未确认）
