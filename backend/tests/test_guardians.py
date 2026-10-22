"""守护人：增删改查、数量限制、邮箱校验与越权保护。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_empty_list(client: TestClient, account: dict) -> None:
    data = client.get("/api/guardians", headers=account["headers"]).json()["data"]
    assert data["items"] == []
    assert data["maxCount"] == 3
    assert data["remaining"] == 3


def test_create_update_delete(client: TestClient, account: dict) -> None:
    created = client.post(
        "/api/guardians",
        headers=account["headers"],
        json={"name": "妈妈", "email": "Mom@Example.com", "relation": "family"},
    )
    assert created.status_code == 201
    guardian = created.json()["data"]
    assert guardian["id"]
    assert guardian["email"] == "mom@example.com"  # 统一小写
    assert guardian["relation"] == "family"

    updated = client.put(
        f"/api/guardians/{guardian['id']}",
        headers=account["headers"],
        json={"name": "母亲", "email": "mother@example.com"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "母亲"
    assert updated.json()["data"]["email"] == "mother@example.com"

    listing = client.get("/api/guardians", headers=account["headers"]).json()["data"]
    assert listing["remaining"] == 2

    removed = client.delete(f"/api/guardians/{guardian['id']}", headers=account["headers"])
    assert removed.status_code == 200
    assert client.get("/api/guardians", headers=account["headers"]).json()["data"]["items"] == []


def test_max_three_guardians(client: TestClient, account: dict) -> None:
    for index in range(3):
        resp = client.post(
            "/api/guardians",
            headers=account["headers"],
            json={"name": f"守护人{index}", "email": f"g{index}@example.com"},
        )
        assert resp.status_code == 201

    overflow = client.post(
        "/api/guardians",
        headers=account["headers"],
        json={"name": "第四位", "email": "g4@example.com"},
    )
    assert overflow.status_code == 409
    assert overflow.json()["code"] == "GUARDIAN_LIMIT"


def test_duplicate_email_rejected(client: TestClient, account: dict) -> None:
    payload = {"name": "爸爸", "email": "dad@example.com"}
    assert client.post("/api/guardians", headers=account["headers"], json=payload).status_code == 201

    dup = client.post("/api/guardians", headers=account["headers"], json=payload)
    assert dup.status_code == 409
    assert dup.json()["code"] == "GUARDIAN_EMAIL_DUPLICATE"

    # 大小写不同视为同一邮箱
    dup2 = client.post(
        "/api/guardians",
        headers=account["headers"],
        json={"name": "爸爸2", "email": "DAD@Example.com"},
    )
    assert dup2.status_code == 409


def test_update_to_existing_email_rejected(client: TestClient, account: dict) -> None:
    a = client.post(
        "/api/guardians", headers=account["headers"], json={"name": "A", "email": "a@x.com"}
    ).json()["data"]
    client.post(
        "/api/guardians", headers=account["headers"], json={"name": "B", "email": "b@x.com"}
    )
    resp = client.put(
        f"/api/guardians/{a['id']}", headers=account["headers"], json={"email": "b@x.com"}
    )
    assert resp.status_code == 409


def test_invalid_email_rejected(client: TestClient, account: dict) -> None:
    resp = client.post(
        "/api/guardians",
        headers=account["headers"],
        json={"name": "无效", "email": "not-an-email"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_blank_name_rejected(client: TestClient, account: dict) -> None:
    resp = client.post(
        "/api/guardians",
        headers=account["headers"],
        json={"name": "   ", "email": "c@x.com"},
    )
    assert resp.status_code == 422


def test_delete_missing_guardian(client: TestClient, account: dict) -> None:
    resp = client.delete("/api/guardians/99999", headers=account["headers"])
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"
