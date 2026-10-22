"""接口契约、数据库约束与异常处理。"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import Account, CheckinRecord, SafetyAlert
from app.models.base import utcnow
from app.services.timeutil import now_utc


def test_success_envelope_shape(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert set(body.keys()) == {"code", "message", "data", "requestId"}
    assert body["code"] == "OK"
    assert body["message"] == "success"


def test_error_envelope_shape(client: TestClient) -> None:
    body = client.get("/api/account/me").json()
    assert body["code"] == "UNAUTHORIZED"
    assert body["data"] is None
    assert body["message"]


def test_request_id_is_echoed(client: TestClient) -> None:
    resp = client.get("/api/health", headers={"X-Request-ID": "trace-abc-123"})
    assert resp.headers["X-Request-ID"] == "trace-abc-123"
    assert resp.json()["requestId"] == "trace-abc-123"
    assert resp.headers["X-Response-Time"].isdigit()


def test_unknown_route_returns_envelope(client: TestClient) -> None:
    resp = client.get("/api/not-exist")
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


def test_openapi_available(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    for path in ("/api/account/init", "/api/checkin", "/api/checkin/history", "/api/guardians"):
        assert path in schema["paths"]


def test_checkin_idempotency_unique_constraint(session: Session, client: TestClient) -> None:
    client.post("/api/account/init", json={"initKey": uuid.uuid4().hex})
    account = session.exec(select(Account)).one()
    now = now_utc()
    session.add(
        CheckinRecord(
            account_id=account.id,
            checked_in_at=now,
            idempotency_key="dup-key-0001",
        )
    )
    session.commit()

    session.add(
        CheckinRecord(
            account_id=account.id,
            checked_in_at=now,
            idempotency_key="dup-key-0001",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_alert_unique_per_due(session: Session, client: TestClient) -> None:
    client.post("/api/account/init", json={"initKey": uuid.uuid4().hex})
    account = session.exec(select(Account)).one()
    due = utcnow()
    session.add(SafetyAlert(account_id=account.id, due_at=due, triggered_at=due))
    session.commit()

    session.add(SafetyAlert(account_id=account.id, due_at=due, triggered_at=due))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_guardian_limit_config(client: TestClient, account: dict) -> None:
    data = client.get("/api/guardians", headers=account["headers"]).json()["data"]
    assert data["maxCount"] == 3


def test_bad_debug_time_header(client: TestClient, account: dict) -> None:
    resp = client.get(
        "/api/checkin/status",
        headers={**account["headers"], "X-Debug-Now": "not-a-date"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_dev_scheduler_requires_auth(client: TestClient) -> None:
    """调试接口也要鉴权，避免调试镜像暴露到公网后被匿名触发。"""
    resp = client.post("/api/dev/scheduler/run")
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


# ---------- 前端页面托管的安全约束 ----------


def test_root_does_not_serve_frontend_outside_dev(client: TestClient) -> None:
    """非 dev 环境下 `/` 只返回 API 信息，不返回任何前端页面。"""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "在吗 API"
    assert "前端页面" in body["hint"]
    assert "text/html" not in resp.headers.get("content-type", "")


def test_static_paths_are_404_outside_dev(client: TestClient) -> None:
    """未托管时，静态目录下的任何路径都不可访问。"""
    for path in ("/index.html", "/assets/index.js", "/pages/index/index", "/manifest.json"):
        resp = client.get(path)
        assert resp.status_code == 404, path
        assert resp.json()["code"] == "NOT_FOUND"


def test_resolve_static_root_only_in_dev(tmp_path, monkeypatch) -> None:
    from app.core.config import settings
    from app.main import resolve_static_root

    (tmp_path / "index.html").write_text("<html><div id='app'></div></html>", encoding="utf-8")
    monkeypatch.setattr(settings, "STATIC_DIR", str(tmp_path))

    for env in ("prod", "test"):
        monkeypatch.setattr(settings, "APP_ENV", env)
        assert resolve_static_root() is None, f"{env} 环境不应托管前端"

    monkeypatch.setattr(settings, "APP_ENV", "dev")
    assert resolve_static_root() == tmp_path.resolve()

    # dev 但目录内没有 index.html
    monkeypatch.setattr(settings, "STATIC_DIR", str(tmp_path / "empty"))
    assert resolve_static_root() is None

    # 未配置 STATIC_DIR
    monkeypatch.setattr(settings, "STATIC_DIR", "")
    assert resolve_static_root() is None


def test_static_access_key_is_optional(monkeypatch) -> None:
    """未配置口令时放行；配置后必须匹配（URL 参数或 Cookie 均可）。"""
    from app.core.config import settings
    from app.main import static_access_ok

    monkeypatch.setattr(settings, "STATIC_ACCESS_KEY", "")
    assert static_access_ok(None, None) is True
    assert static_access_ok("anything", None) is True

    monkeypatch.setattr(settings, "STATIC_ACCESS_KEY", "s3cret-key")
    assert static_access_ok(None, None) is False
    assert static_access_ok("", None) is False
    assert static_access_ok("wrong", None) is False
    assert static_access_ok("s3cret-key", None) is True
    assert static_access_ok(None, "s3cret-key") is True
    assert static_access_ok(None, "wrong") is False
