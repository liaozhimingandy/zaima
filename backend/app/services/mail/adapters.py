"""邮件发送：统一接口 + SMTP 适配器 + 开发环境模拟适配器。"""

from __future__ import annotations

import smtplib
import ssl
import uuid
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage as StdEmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmailNotConfigured(RuntimeError):
    """生产环境缺少 SMTP 配置：必须显式失败，禁止伪造成功。"""


@dataclass
class OutgoingEmail:
    to_email: str
    to_name: str
    subject: str
    text_body: str
    html_body: str | None = None
    reply_to: str | None = None


@dataclass
class SendResult:
    ok: bool
    simulated: bool = False
    provider_id: str | None = None
    error: str | None = None
    sent_at: datetime | None = None


class EmailSender(Protocol):
    name: str

    def send(self, message: OutgoingEmail) -> SendResult:  # pragma: no cover - 协议定义
        ...


def _build_mime(message: OutgoingEmail) -> StdEmailMessage:
    mime = StdEmailMessage()
    mime["Subject"] = message.subject
    mime["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM))
    mime["To"] = formataddr((message.to_name or "", message.to_email))
    mime["Date"] = formatdate(localtime=False)
    mime["Message-ID"] = make_msgid(domain="zaima.local")
    if message.reply_to:
        mime["Reply-To"] = message.reply_to
    mime.set_content(message.text_body, subtype="plain", charset="utf-8")
    if message.html_body:
        mime.add_alternative(message.html_body, subtype="html", charset="utf-8")
    return mime


class SmtpEmailSender:
    """真实 SMTP 发送。

    - 465 端口默认使用 SSL
    - 587 等端口使用 STARTTLS
    - 连接/超时/认证失败都会抛出可读异常，由上层记录并重试
    """

    name = "smtp"

    def __init__(self) -> None:
        if not settings.SMTP_HOST or not settings.SMTP_FROM:
            raise EmailNotConfigured("未配置 SMTP_HOST / SMTP_FROM，无法发送邮件")

    def send(self, message: OutgoingEmail) -> SendResult:
        mime = _build_mime(message)
        host = settings.SMTP_HOST
        port = settings.SMTP_PORT
        timeout = settings.SMTP_TIMEOUT_SECONDS
        try:
            if settings.SMTP_USE_TLS and port == 465:
                with smtplib.SMTP_SSL(
                    host, port, timeout=timeout, context=ssl.create_default_context()
                ) as server:
                    self._login(server)
                    server.send_message(mime)
            else:
                with smtplib.SMTP(host, port, timeout=timeout) as server:
                    server.ehlo()
                    if settings.SMTP_USE_TLS:
                        server.starttls(context=ssl.create_default_context())
                        server.ehlo()
                    self._login(server)
                    server.send_message(mime)
            logger.info("邮件发送成功 to=%s", _mask_email(message.to_email))
            return SendResult(ok=True, provider_id=mime.get("Message-ID"))
        except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
            logger.warning("邮件发送失败 to=%s err=%s", _mask_email(message.to_email), exc)
            return SendResult(ok=False, error=f"{type(exc).__name__}: {exc}"[:500])

    def _login(self, server: smtplib.SMTP) -> None:
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)


class MockEmailSender:
    """开发/测试环境模拟发送：把邮件写入本地目录，返回 simulated=True。

    严禁在生产环境使用；工厂函数会拦截。
    """

    name = "mock"

    def __init__(self, directory: str | None = None) -> None:
        self.directory = Path(directory or settings.EMAIL_MOCK_DIR)
        self.directory.mkdir(parents=True, exist_ok=True)

    def send(self, message: OutgoingEmail) -> SendResult:
        mime = _build_mime(message)
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}.eml"
        path = self.directory / filename
        path.write_bytes(bytes(mime))
        logger.info("模拟邮件已写入 %s to=%s", path, _mask_email(message.to_email))
        return SendResult(ok=True, simulated=True, provider_id=filename)


def get_sender() -> EmailSender:
    adapter = settings.EMAIL_ADAPTER
    if settings.is_prod and adapter != "smtp":
        raise EmailNotConfigured("生产环境必须使用 smtp 适配器")
    if adapter == "mock":
        return MockEmailSender()
    return SmtpEmailSender()


def _mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        return f"{name[0]}***@{domain}"
    return f"{name[:2]}***@{domain}"
