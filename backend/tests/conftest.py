"""pytest 全局配置。

测试库优先使用 ``TEST_DATABASE_URL``（PostgreSQL），未提供时退化为本地 SQLite。
两种模式共用同一套断言，避免「只在 SQLite 上通过」的假绿灯。
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="zaima-test-"))

os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "false"
os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["EMAIL_ADAPTER"] = "mock"
os.environ["EMAIL_MOCK_DIR"] = str(_TMP / "mailbox")
os.environ["ALLOW_TIME_TRAVEL"] = "true"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["DOCS_ENABLED"] = "true"

if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
else:
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{(_TMP / 'test.db').as_posix()}"

from sqlmodel import Session, SQLModel  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.db import get_engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    engine = get_engine()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_tables(_database: None) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        for table in reversed(SQLModel.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture()
def session() -> Session:
    with Session(get_engine()) as s:
        yield s


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def account(client) -> dict:
    """创建一个匿名账户，返回 headers / accountId。"""
    init_key = uuid.uuid4().hex
    resp = client.post(
        "/api/account/init",
        json={"initKey": init_key, "platform": "test", "appVersion": "1.0.0"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    token = body["data"]["accessToken"]
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "token": token,
        "accountId": body["data"]["accountId"],
        "initKey": init_key,
    }


@pytest.fixture()
def other_account(client) -> dict:
    init_key = uuid.uuid4().hex
    resp = client.post(
        "/api/account/init",
        json={"initKey": init_key, "platform": "test"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["data"]["accessToken"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "token": token}
