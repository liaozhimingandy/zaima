"""健康检查。"""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.core.config import settings
from app.core.db import check_db
from app.core.response import ok
from app.services.timeutil import iso_utc, now_utc

router = APIRouter(tags=["system"])


@router.get("/health", summary="健康检查")
def health() -> dict:
    db_ok, db_error = check_db()
    return ok(
        {
            "status": "ok" if db_ok else "degraded",
            "version": __version__,
            "env": settings.APP_ENV,
            "database": {"ok": db_ok, "error": None if db_ok else "unavailable"},
            "emailAdapter": settings.EMAIL_ADAPTER,
            "schedulerEnabled": settings.SCHEDULER_ENABLED,
            "serverTime": iso_utc(now_utc()),
        }
    )
