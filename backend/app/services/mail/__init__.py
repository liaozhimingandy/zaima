"""邮件发送模块入口。"""

from app.core.config import settings
from app.services.mail.adapters import (
    EmailNotConfigured,
    EmailSender,
    MockEmailSender,
    OutgoingEmail,
    SendResult,
    SmtpEmailSender,
    get_sender,
)
from app.services.mail.templates import AlertEmailContext, render_alert_email

__all__ = [
    "AlertEmailContext",
    "EmailNotConfigured",
    "EmailSender",
    "MockEmailSender",
    "OutgoingEmail",
    "SendResult",
    "SmtpEmailSender",
    "get_sender",
    "render_alert_email",
    "settings",
]
