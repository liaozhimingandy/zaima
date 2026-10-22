"""提醒阶段、异常事件与通知的端到端闭环。

时间轴（默认规则 08:00 / 08:30 / 12:00 / 20:00 / 次日 08:00）：
- 2026-03-01T00:00Z 确认（上海 03-01 08:00）
- 应确认 2026-03-02T00:00Z
- 异常事件 2026-03-03T00:00Z
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

CHECKIN_AT = "2026-03-01T00:00:00Z"
DUE_AT = "2026-03-02T00:00:00Z"
ALERT_AT = "2026-03-03T00:00:00Z"


def _hdr(account: dict, now: str | None = None) -> dict:
    headers = dict(account["headers"])
    if now:
        headers["X-Debug-Now"] = now
    return headers


def _run_scheduler(client: TestClient, account: dict, now: str, dispatch: bool = True) -> dict:
    resp = client.post(
        f"/api/dev/scheduler/run?dispatch={'true' if dispatch else 'false'}",
        headers=_hdr(account, now),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _setup(client: TestClient, account: dict) -> dict:
    """添加一名守护人并在固定时间确认一次。"""
    guardian = client.post(
        "/api/guardians",
        headers=account["headers"],
        json={"name": "妈妈", "email": "mom@example.com", "relation": "family"},
    )
    assert guardian.status_code == 201, guardian.text
    resp = client.post(
        "/api/checkin", headers=_hdr(account, CHECKIN_AT), json={"requestId": uuid.uuid4().hex}
    )
    assert resp.status_code == 200
    return guardian.json()["data"]


def test_no_alert_before_threshold(client: TestClient, account: dict) -> None:
    _setup(client, account)
    result = _run_scheduler(client, account, "2026-03-02T23:59:00Z")
    assert result["scan"]["alertsCreated"] == 0
    assert result["dispatch"]["picked"] == 0


def test_reminder_stage_does_not_send_email(client: TestClient, account: dict) -> None:
    _setup(client, account)
    # 第一次提醒 08:30
    status = client.get("/api/checkin/status", headers=_hdr(account, "2026-03-02T00:30:00Z")).json()["data"]
    assert status["stage"] == "REMINDING"
    assert status["remindersPassed"] == 1
    result = _run_scheduler(client, account, "2026-03-02T00:30:00Z")
    assert result["scan"]["alertsCreated"] == 0
    assert result["dispatch"]["picked"] == 0


def test_alert_created_and_email_sent(client: TestClient, account: dict) -> None:
    _setup(client, account)
    result = _run_scheduler(client, account, ALERT_AT)
    assert result["scan"]["alertsCreated"] == 1
    assert result["scan"]["notificationsCreated"] == 1
    assert result["dispatch"]["sent"] == 1
    assert result["dispatch"]["simulated"] == 1  # 测试环境为模拟发送

    status = client.get("/api/checkin/status", headers=_hdr(account, ALERT_AT)).json()["data"]
    assert status["stage"] == "ALERT"
    assert status["hasOpenAlert"] is True
    assert status["openAlert"]["guardianCount"] == 1

    records = client.get("/api/dev/notifications", headers=_hdr(account, ALERT_AT)).json()["data"]
    assert len(records["items"]) == 1
    item = records["items"][0]
    assert item["status"] == "sent"
    assert item["simulated"] is True
    assert item["recipient"] == "mom@example.com"
    assert item["attempts"] == 1


def test_scheduler_is_idempotent(client: TestClient, account: dict) -> None:
    _setup(client, account)
    first = _run_scheduler(client, account, ALERT_AT)
    assert first["scan"]["alertsCreated"] == 1

    for _ in range(3):
        again = _run_scheduler(client, account, "2026-03-03T00:30:00Z")
        assert again["scan"]["alertsCreated"] == 0
        assert again["scan"]["alertsExisting"] == 1
        assert again["scan"]["notificationsCreated"] == 0
        assert again["dispatch"]["picked"] == 0

    records = client.get("/api/dev/notifications", headers=_hdr(account, ALERT_AT)).json()["data"]
    assert len(records["items"]) == 1


def test_checkin_resolves_alert(client: TestClient, account: dict) -> None:
    _setup(client, account)
    _run_scheduler(client, account, ALERT_AT)

    resp = client.post(
        "/api/checkin",
        headers=_hdr(account, "2026-03-03T02:00:00Z"),
        json={"requestId": uuid.uuid4().hex},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["resolvedAlert"] is True
    assert data["status"]["stage"] == "NORMAL"
    assert data["status"]["hasOpenAlert"] is False
    assert data["status"]["nextCheckinAt"].startswith("2026-03-04T00:00:00")


def test_checkin_cancels_pending_notifications(client: TestClient, account: dict) -> None:
    _setup(client, account)
    # 只扫描不派发：通知任务停留在 pending
    result = _run_scheduler(client, account, ALERT_AT, dispatch=False)
    assert result["scan"]["notificationsCreated"] == 1

    client.post(
        "/api/checkin",
        headers=_hdr(account, "2026-03-03T01:00:00Z"),
        json={"requestId": uuid.uuid4().hex},
    )
    records = client.get("/api/dev/notifications", headers=_hdr(account, ALERT_AT)).json()["data"]
    assert records["items"][0]["status"] == "cancelled"

    # 恢复后即使再次扫描也不会补发旧事件
    again = _run_scheduler(client, account, "2026-03-03T01:05:00Z")
    assert again["scan"]["alertsCreated"] == 0
    assert again["dispatch"]["picked"] == 0


def test_multiple_guardians_all_notified(client: TestClient, account: dict) -> None:
    for index, email in enumerate(["a@example.com", "b@example.com", "c@example.com"]):
        client.post(
            "/api/guardians",
            headers=account["headers"],
            json={"name": f"守护人{index}", "email": email},
        )
    client.post(
        "/api/checkin", headers=_hdr(account, CHECKIN_AT), json={"requestId": uuid.uuid4().hex}
    )

    result = _run_scheduler(client, account, ALERT_AT)
    assert result["scan"]["notificationsCreated"] == 3
    assert result["dispatch"]["sent"] == 3

    records = client.get("/api/dev/notifications", headers=_hdr(account, ALERT_AT)).json()["data"]
    assert {item["recipient"] for item in records["items"]} == {
        "a@example.com",
        "b@example.com",
        "c@example.com",
    }
    assert all(item["status"] == "sent" for item in records["items"])


def test_no_guardian_means_no_notification(client: TestClient, account: dict) -> None:
    client.post(
        "/api/checkin", headers=_hdr(account, CHECKIN_AT), json={"requestId": uuid.uuid4().hex}
    )
    result = _run_scheduler(client, account, ALERT_AT)
    assert result["scan"]["alertsCreated"] == 1
    assert result["scan"]["skippedNoGuardian"] == 1
    assert result["scan"]["notificationsCreated"] == 0

    status = client.get("/api/checkin/status", headers=_hdr(account, ALERT_AT)).json()["data"]
    assert status["stage"] == "ALERT"
    assert status["openAlert"]["guardianCount"] == 0


def test_other_account_alert_not_affected(client: TestClient, account: dict, other_account: dict) -> None:
    _setup(client, account)
    _run_scheduler(client, account, ALERT_AT)

    # 另一个账户仍处于正常状态
    other = client.get("/api/checkin/status", headers=_hdr(other_account, ALERT_AT)).json()["data"]
    assert other["hasOpenAlert"] is False
    assert other["stage"] in ("NORMAL", "PENDING", "REMINDING")


def _create_due_account(client: TestClient, index: int) -> None:
    init = client.post(
        "/api/account/init",
        json={"initKey": f"batch-test-{uuid.uuid4().hex}", "platform": "test"},
    )
    headers = {"Authorization": f"Bearer {init.json()['data']['accessToken']}"}
    client.post(
        "/api/guardians",
        headers=headers,
        json={"name": f"守护人{index}", "email": f"batch{index}@example.com"},
    )
    resp = client.post(
        "/api/checkin",
        headers={**headers, "X-Debug-Now": CHECKIN_AT},
        json={"requestId": uuid.uuid4().hex},
    )
    assert resp.status_code == 200


def test_scan_covers_accounts_beyond_batch_size(client: TestClient, session) -> None:
    """账户数超过单批上限时，必须全部被扫描到（键集分页）。"""
    from datetime import datetime

    from app.services.alert_service import scan_once

    for index in range(3):
        _create_due_account(client, index)

    stats = scan_once(session, now=datetime.fromisoformat(ALERT_AT.replace("Z", "+00:00")), limit=1)
    assert stats.scanned == 3
    assert stats.alerts_created == 3
    assert stats.notifications_created == 3
    assert stats.errors == []
