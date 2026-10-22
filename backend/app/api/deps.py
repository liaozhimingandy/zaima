"""路由公共依赖。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlmodel import Session

from app.core.config import settings
from app.core.db import get_session
from app.core.errors import ValidationError
from app.models import Account
from app.services.account_service import authenticate
from app.services.timeutil import ensure_utc, now_utc

SessionDep = Annotated[Session, Depends(get_session)]


def _debug_now(request: Request) -> datetime | None:
    """开发/测试环境允许通过请求头模拟时间推进（生产环境该能力关闭）。"""
    if not settings.ALLOW_TIME_TRAVEL or settings.is_prod:
        return None
    raw = request.headers.get("X-Debug-Now")
    if not raw:
        return None
    try:
        value = raw.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError("X-Debug-Now 需为 ISO8601 时间") from exc
    return ensure_utc(parsed)


def get_now(request: Request) -> datetime:
    return _debug_now(request) or now_utc()


NowDep = Annotated[datetime, Depends(get_now)]


def get_current_account(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Account:
    return authenticate(session, authorization)


CurrentAccount = Annotated[Account, Depends(get_current_account)]
