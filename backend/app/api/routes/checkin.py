"""确认（我在）相关接口。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentAccount, NowDep, SessionDep
from app.core.response import ok_model
from app.schemas.checkin import (
    CheckinCreateRequest,
    CheckinCreateResponse,
    CheckinSettingRead,
    CheckinSettingUpdate,
    CheckinStatusRead,
)
from app.services.checkin_service import (
    anchor_for,
    build_status,
    create_checkin,
    last_checkin_at,
    list_history,
)
from app.services.setting_service import build_setting_read, get_setting, update_setting

router = APIRouter(prefix="/checkin", tags=["checkin"])


@router.get("/settings", summary="获取确认设置")
def read_settings(account: CurrentAccount, session: SessionDep) -> dict:
    setting = get_setting(session, account)
    anchor = anchor_for(account, last_checkin_at(session, account.id))  # type: ignore[arg-type]
    return ok_model(build_setting_read(setting, anchor))


@router.put("/settings", summary="修改确认设置")
def put_settings(
    payload: CheckinSettingUpdate,
    account: CurrentAccount,
    session: SessionDep,
) -> dict:
    setting = update_setting(session, account, payload)
    anchor = anchor_for(account, last_checkin_at(session, account.id))  # type: ignore[arg-type]
    return ok_model(build_setting_read(setting, anchor), message="设置已更新")


@router.get("/status", summary="获取当前确认状态")
def read_status(account: CurrentAccount, session: SessionDep, now: NowDep) -> dict:
    status_payload: CheckinStatusRead = build_status(session, account, now=now)
    return ok_model(status_payload)


@router.post("", summary="我在（确认）")
def post_checkin(
    payload: CheckinCreateRequest,
    account: CurrentAccount,
    session: SessionDep,
    now: NowDep,
) -> dict:
    record, duplicated, resolved = create_checkin(session, account, payload, now=now)
    status_payload = build_status(session, account, now=now)
    return ok_model(
        CheckinCreateResponse(
            record={
                "id": record.id,
                "checked_in_at": record.checked_in_at,
                "client_time": record.client_time,
                "due_at": record.due_at,
                "source": record.source,
                "note": record.note,
            },
            duplicated=duplicated,
            resolved_alert=resolved > 0,
            status=status_payload,
        ),
        message="已记录你的确认" if not duplicated else "该确认已记录",
    )


@router.get("/history", summary="确认历史（游标分页）")
def read_history(
    account: CurrentAccount,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> dict:
    return ok_model(list_history(session, account, limit=limit, cursor=cursor))
