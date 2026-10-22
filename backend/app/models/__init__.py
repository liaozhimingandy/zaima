"""模型注册入口。"""

from app.models.account import Account
from app.models.checkin import CheckinRecord, CheckinSetting
from app.models.guardian import Guardian
from app.models.notification import NotificationRecord, SafetyAlert

__all__ = [
    "Account",
    "CheckinRecord",
    "CheckinSetting",
    "Guardian",
    "NotificationRecord",
    "SafetyAlert",
]
