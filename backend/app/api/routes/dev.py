"""开发/联调辅助接口（生产环境不注册）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentAccount, NowDep, SessionDep
from app.core.config import settings
from app.core.logging import get_logger
from app.core.response import ok_model
from app.models import NotificationRecord
from sqlmodel import select
from app.services.alert_service import scan_once
from app.services.notification_service import dispatch_pending

logger = get_logger(__name__)

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/scheduler/run", summary="手动触发一次扫描与派发（含时间模拟）")
def run_scheduler(
    account: CurrentAccount,
    session: SessionDep,
    now: NowDep,
    dispatch: Annotated[bool, Query()] = True,
) -> dict:
    # 扫描范围是全局的（所有账户），这里仍要求携带有效账户凭证，
    # 避免调试镜像暴露到公网后被匿名触发。
    logger.info("手动触发调度 account_id=%s dispatch=%s", account.public_id, dispatch)
    scan = scan_once(session, now=now)
    result = {"scan": scan.as_dict(), "dispatch": None, "now": now.isoformat()}
    if dispatch:
        result["dispatch"] = dispatch_pending(session, now=now).as_dict()
    return ok_model(result)


@router.get("/notifications", summary="查看当前账户的通知任务")
def list_notifications(
    account: CurrentAccount,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    rows = list(
        session.exec(
            select(NotificationRecord)
            .where(NotificationRecord.account_id == account.id)
            .order_by(NotificationRecord.id.desc())  # type: ignore[attr-defined]
            .limit(limit)
        ).all()
    )
    return ok_model(
        {
            "adapter": settings.EMAIL_ADAPTER,
            "items": [
                {
                    "id": row.id,
                    "alertId": row.alert_id,
                    "guardianId": row.guardian_id,
                    "recipient": row.recipient_email,
                    "status": row.status,
                    "attempts": row.attempts,
                    "maxAttempts": row.max_attempts,
                    "simulated": row.simulated,
                    "lastError": row.last_error,
                    "sentAt": row.sent_at.isoformat() if row.sent_at else None,
                    "nextAttemptAt": row.next_attempt_at.isoformat(),
                }
                for row in rows
            ],
        }
    )
