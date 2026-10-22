"""邮件适配器、重试、去重与故障恢复。"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import NotificationRecord
from app.models.enums import NotificationStatus
from app.services.mail import (
    EmailNotConfigured,
    MockEmailSender,
    OutgoingEmail,
    SendResult,
)
from app.services.notification_service import dispatch_pending
from app.services.timeutil import now_utc

CHECKIN_AT = "2026-03-01T00:00:00Z"
ALERT_AT = "2026-03-03T00:00:00Z"


def hdr(account: dict, now: str) -> dict:
    headers = dict(account["headers"])
    headers["X-Debug-Now"] = now
    return headers


def prepare_alert(client: TestClient, account: dict, *, dispatch: bool = False) -> None:
    client.post(
        "/api/guardians",
        headers=account["headers"],
        json={"name": "妈妈", "email": "mom@example.com"},
    )
    client.post(
        "/api/checkin", headers=hdr(account, CHECKIN_AT), json={"requestId": uuid.uuid4().hex}
    )
    resp = client.post(
        f"/api/dev/scheduler/run?dispatch={'true' if dispatch else 'false'}",
        headers=hdr(account, ALERT_AT),
    )
    assert resp.status_code == 200, resp.text


def test_mock_sender_writes_eml(tmp_path) -> None:
    sender = MockEmailSender(str(tmp_path / "mailbox"))
    result = sender.send(
        OutgoingEmail(
            to_email="mom@example.com",
            to_name="妈妈",
            subject="测试主题",
            text_body="正文",
            html_body="<p>正文</p>",
        )
    )
    assert result.ok is True
    assert result.simulated is True
    files = list((tmp_path / "mailbox").glob("*.eml"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8", errors="ignore")
    assert "mom@example.com" in content


def test_config_missing_is_permanent_failure(client: TestClient, account: dict, monkeypatch) -> None:
    prepare_alert(client, account)

    def _raise() -> None:
        raise EmailNotConfigured("未配置 SMTP_HOST")

    monkeypatch.setattr("app.services.notification_service.get_sender", _raise)

    with Session(_engine()) as session:
        stats = dispatch_pending(session, now=_dt(ALERT_AT))
    assert stats.failed == 1
    assert stats.sent == 0

    rows = _records()
    assert rows[0].status == NotificationStatus.FAILED.value
    assert "邮件服务未正确配置" in (rows[0].last_error or "")


class FlakySender:
    name = "flaky"

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    def send(self, message: OutgoingEmail) -> SendResult:
        self.calls += 1
        if self.calls <= self.fail_times:
            return SendResult(ok=False, error="SMTP connect timeout")
        return SendResult(ok=True, simulated=True)


def test_retry_until_success(client: TestClient, account: dict, monkeypatch) -> None:
    prepare_alert(client, account)
    sender = FlakySender(fail_times=2)
    monkeypatch.setattr("app.services.notification_service.get_sender", lambda: sender)

    engine = _engine()
    moment = _dt(ALERT_AT)
    with Session(engine) as session:
        first = dispatch_pending(session, now=moment)
    assert first.retry_scheduled == 1
    record = _records()[0]
    assert record.status == NotificationStatus.PENDING.value
    assert record.attempts == 1
    assert record.next_attempt_at > moment

    # 未到重试时间：不会被再次取到
    with Session(engine) as session:
        idle = dispatch_pending(session, now=moment + timedelta(seconds=5))
    assert idle.picked == 0

    with Session(engine) as session:
        second = dispatch_pending(session, now=moment + timedelta(seconds=61))
    assert second.retry_scheduled == 1

    with Session(engine) as session:
        third = dispatch_pending(session, now=moment + timedelta(seconds=200))
    assert third.sent == 1
    record = _records()[0]
    assert record.status == NotificationStatus.SENT.value
    assert record.attempts == 3
    assert sender.calls == 3


def test_max_attempts_marks_failed(client: TestClient, account: dict, monkeypatch) -> None:
    prepare_alert(client, account)
    sender = FlakySender(fail_times=99)
    monkeypatch.setattr("app.services.notification_service.get_sender", lambda: sender)

    engine = _engine()
    moment = _dt(ALERT_AT)
    for offset in (0, 61, 200):
        with Session(engine) as session:
            dispatch_pending(session, now=moment + timedelta(seconds=offset))

    record = _records()[0]
    assert record.status == NotificationStatus.FAILED.value
    assert record.attempts == record.max_attempts
    assert "timeout" in (record.last_error or "")

    # 失败后不再重试
    with Session(engine) as session:
        assert dispatch_pending(session, now=moment + timedelta(hours=5)).picked == 0


def test_stale_sending_is_recovered(client: TestClient, account: dict, monkeypatch) -> None:
    prepare_alert(client, account)
    engine = _engine()

    # 模拟进程在发送中崩溃
    with Session(engine) as session:
        record = session.exec(select(NotificationRecord)).one()
        record.status = NotificationStatus.SENDING.value
        record.attempts = 1
        record.last_attempt_at = _dt(ALERT_AT) - timedelta(minutes=30)
        session.add(record)
        session.commit()

    monkeypatch.setattr(
        "app.services.notification_service.get_sender", lambda: MockEmailSender()
    )
    with Session(engine) as session:
        stats = dispatch_pending(session, now=_dt(ALERT_AT))
    assert stats.sent == 1
    assert _records()[0].status == NotificationStatus.SENT.value


def test_dedupe_key_prevents_duplicate_tasks(client: TestClient, account: dict) -> None:
    prepare_alert(client, account, dispatch=False)
    # 再次扫描不应生成第二条任务
    client.post("/api/dev/scheduler/run?dispatch=false", headers=hdr(account, ALERT_AT))
    rows = _records()
    assert len(rows) == 1
    assert rows[0].dedupe_key.startswith("alert:")


def test_production_requires_smtp_adapter(monkeypatch) -> None:
    from app.services.mail.adapters import get_sender

    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.setattr(settings, "EMAIL_ADAPTER", "mock")
    with pytest.raises(EmailNotConfigured):
        get_sender()


# ---------- helpers ----------


def _engine():
    from app.core.db import get_engine

    return get_engine()


def _dt(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _records() -> list[NotificationRecord]:
    with Session(_engine()) as session:
        return list(session.exec(select(NotificationRecord).order_by(NotificationRecord.id)).all())
