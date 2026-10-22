"""确认业务：状态、确认、幂等、历史与设置。"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

NOW = "2026-03-01T00:00:00Z"  # 上海 2026-03-01 08:00


def hdr(account: dict, now: str | None = NOW) -> dict:
    headers = dict(account["headers"])
    if now:
        headers["X-Debug-Now"] = now
    return headers


def test_default_status_is_normal(client: TestClient, account: dict) -> None:
    resp = client.get("/api/checkin/status", headers=hdr(account, None))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["stage"] == "NORMAL"
    assert data["periodDays"] == 1
    assert data["guardianCount"] == 0
    assert data["hasOpenAlert"] is False
    assert data["lastCheckinAt"] is None
    assert data["nextCheckinAt"]
    assert len(data["reminders"]) == 3


def test_checkin_updates_status_and_creates_record(client: TestClient, account: dict) -> None:
    rid = uuid.uuid4().hex
    resp = client.post("/api/checkin", headers=hdr(account), json={"requestId": rid})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["duplicated"] is False
    assert data["record"]["checkedInAt"].startswith("2026-03-01T00:00:00")
    assert data["status"]["stage"] == "NORMAL"
    assert data["status"]["lastCheckinAt"] is not None
    # 确认后下次应确认时间为次日同一时刻
    assert data["status"]["nextCheckinAt"].startswith("2026-03-02T00:00:00")


def test_duplicate_request_does_not_create_second_record(client: TestClient, account: dict) -> None:
    rid = uuid.uuid4().hex
    first = client.post("/api/checkin", headers=hdr(account), json={"requestId": rid})
    second = client.post("/api/checkin", headers=hdr(account), json={"requestId": rid})
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["duplicated"] is True
    assert second.json()["data"]["record"]["id"] == first.json()["data"]["record"]["id"]

    history = client.get("/api/checkin/history", headers=hdr(account, None)).json()["data"]
    assert len(history["items"]) == 1


def test_server_time_wins_over_client_time(client: TestClient, account: dict) -> None:
    """客户端上报一个未来时间，不得影响服务端判定。"""
    resp = client.post(
        "/api/checkin",
        headers=hdr(account),
        json={"requestId": uuid.uuid4().hex, "clientTime": "2030-01-01T00:00:00Z"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["record"]["clientTime"].startswith("2030-01-01")
    assert data["record"]["checkedInAt"].startswith("2026-03-01")
    assert data["status"]["nextCheckinAt"].startswith("2026-03-02")


def test_history_pagination(client: TestClient, account: dict) -> None:
    for _ in range(5):
        client.post("/api/checkin", headers=hdr(account), json={"requestId": uuid.uuid4().hex})

    page1 = client.get("/api/checkin/history?limit=2", headers=hdr(account, None)).json()["data"]
    assert len(page1["items"]) == 2
    assert page1["hasMore"] is True
    assert page1["nextCursor"]

    page2 = client.get(
        f"/api/checkin/history?limit=2&cursor={page1['nextCursor']}",
        headers=hdr(account, None),
    ).json()["data"]
    assert len(page2["items"]) == 2
    ids1 = {item["id"] for item in page1["items"]}
    ids2 = {item["id"] for item in page2["items"]}
    assert not (ids1 & ids2)

    page3 = client.get(
        f"/api/checkin/history?limit=2&cursor={page2['nextCursor']}",
        headers=hdr(account, None),
    ).json()["data"]
    assert len(page3["items"]) == 1
    assert page3["hasMore"] is False


def test_history_empty_state(client: TestClient, account: dict) -> None:
    data = client.get("/api/checkin/history", headers=hdr(account, None)).json()["data"]
    assert data["items"] == []
    assert data["hasMore"] is False
    assert data["nextCursor"] is None


def test_invalid_cursor_rejected(client: TestClient, account: dict) -> None:
    resp = client.get("/api/checkin/history?cursor=@@@", headers=hdr(account, None))
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("period", [1, 2, 3, 7])
def test_update_period(client: TestClient, account: dict, period: int) -> None:
    resp = client.put(
        "/api/checkin/settings", headers=account["headers"], json={"periodDays": period}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["periodDays"] == period

    status = client.get("/api/checkin/status", headers=hdr(account)).json()["data"]
    assert status["periodDays"] == period


def test_invalid_period_rejected(client: TestClient, account: dict) -> None:
    resp = client.put(
        "/api/checkin/settings", headers=account["headers"], json={"periodDays": 5}
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_invalid_time_and_timezone_rejected(client: TestClient, account: dict) -> None:
    bad_time = client.put(
        "/api/checkin/settings", headers=account["headers"], json={"checkinTime": "8:00"}
    )
    assert bad_time.status_code == 422

    bad_tz = client.put(
        "/api/checkin/settings", headers=account["headers"], json={"timezone": "Mars/Base"}
    )
    assert bad_tz.status_code == 422


def test_timezone_change_shifts_due_time(client: TestClient, account: dict) -> None:
    resp = client.put(
        "/api/checkin/settings",
        headers=account["headers"],
        json={"checkinTime": "21:30", "timezone": "Asia/Tokyo"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["checkinTime"] == "21:30"
    assert data["timezone"] == "Asia/Tokyo"
    # 首次使用以账户创建时间为锚点，此处只校验提醒时刻按本地 21:30 推导
    assert data["reminders"][0]["localAt"].endswith("22:00:00+09:00")


def test_stage_transitions_via_time_travel(client: TestClient, account: dict) -> None:
    client.post(
        "/api/checkin/settings", headers=account["headers"], json={"periodDays": 1}
    )
    client.post("/api/checkin", headers=hdr(account), json={"requestId": uuid.uuid4().hex})

    cases = [
        ("2026-03-01T23:59:00Z", "NORMAL"),
        ("2026-03-02T00:00:00Z", "PENDING"),
        ("2026-03-02T00:30:00Z", "REMINDING"),
        ("2026-03-02T13:00:00Z", "REMINDING"),
        ("2026-03-03T00:00:00Z", "ALERT"),
    ]
    for now, expected in cases:
        data = client.get("/api/checkin/status", headers=hdr(account, now)).json()["data"]
        assert data["stage"] == expected, f"{now} 期望 {expected} 实际 {data['stage']}"
        assert data["stageHint"]
