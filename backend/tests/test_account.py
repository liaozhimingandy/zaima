"""匿名账户：初始化、认证与数据隔离。"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_init_creates_account_with_token(client: TestClient) -> None:
    init_key = uuid.uuid4().hex
    resp = client.post(
        "/api/account/init",
        json={"initKey": init_key, "platform": "h5", "appVersion": "1.0.0"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["code"] == "OK"
    assert body["requestId"]
    data = body["data"]
    assert data["isNew"] is True
    assert data["platform"] == "h5"
    token = data["accessToken"]
    assert token.startswith("zm_")
    # 凭证由 publicId.secret 构成，secret 具备足够长度
    public_id, secret = token[3:].split(".", 1)
    assert len(public_id) >= 10
    assert len(secret) >= 40


def test_duplicate_init_conflicts(client: TestClient) -> None:
    init_key = uuid.uuid4().hex
    payload = {"initKey": init_key, "platform": "h5"}
    assert client.post("/api/account/init", json=payload).status_code == 201
    resp = client.post("/api/account/init", json=payload)
    assert resp.status_code == 409
    assert resp.json()["code"] == "ACCOUNT_EXISTS"


def test_init_rejects_short_key(client: TestClient) -> None:
    resp = client.post("/api/account/init", json={"initKey": "short"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_me_returns_account_and_setting(client: TestClient, account: dict) -> None:
    resp = client.get("/api/account/me", headers=account["headers"])
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["account"]["accountId"] == account["accountId"]
    assert data["setting"]["periodDays"] == 1
    assert data["setting"]["checkinTime"] == "08:00"
    assert data["setting"]["timezone"] == "Asia/Shanghai"
    assert len(data["setting"]["reminders"]) == 3


def test_missing_or_invalid_token_is_rejected(client: TestClient, account: dict) -> None:
    assert client.get("/api/account/me").status_code == 401

    bad = client.get(
        "/api/account/me", headers={"Authorization": "Bearer zm_deadbeef.deadbeefdeadbeef"}
    )
    assert bad.status_code == 401
    assert bad.json()["code"] == "UNAUTHORIZED"

    wrong_secret = account["token"][:-4] + "xxxx"
    resp = client.get("/api/account/me", headers={"Authorization": f"Bearer {wrong_secret}"})
    assert resp.status_code == 401

    malformed = client.get("/api/account/me", headers={"Authorization": "token"})
    assert malformed.status_code == 401


def test_account_data_isolation(client: TestClient, account: dict, other_account: dict) -> None:
    created = client.post(
        "/api/guardians",
        headers=account["headers"],
        json={"name": "妈妈", "email": "mom@example.com"},
    )
    assert created.status_code == 201

    mine = client.get("/api/guardians", headers=account["headers"]).json()["data"]
    theirs = client.get("/api/guardians", headers=other_account["headers"]).json()["data"]
    assert len(mine["items"]) == 1
    assert theirs["items"] == []

    # 使用他人凭证操作本账户守护人必须 404（不做存在性泄露）
    guardian_id = mine["items"][0]["id"]
    resp = client.put(
        f"/api/guardians/{guardian_id}",
        headers=other_account["headers"],
        json={"name": "hacked"},
    )
    assert resp.status_code == 404
    resp = client.delete(f"/api/guardians/{guardian_id}", headers=other_account["headers"])
    assert resp.status_code == 404


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "ok"
    assert data["database"]["ok"] is True
