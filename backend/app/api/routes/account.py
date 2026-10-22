"""匿名账户接口。"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentAccount, SessionDep
from app.core.response import ok_model
from app.schemas.account import AccountInitRequest, AccountInitResponse, AccountPublic
from app.services.account_service import create_account
from app.services.checkin_service import anchor_for, last_checkin_at
from app.services.setting_service import build_setting_read, get_setting

router = APIRouter(prefix="/account", tags=["account"])


@router.post(
    "/init",
    status_code=status.HTTP_201_CREATED,
    summary="初始化匿名账户",
    response_description="返回访问凭证（仅此一次可见，请客户端安全保存）",
)
def init_account(payload: AccountInitRequest, session: SessionDep) -> dict:
    account, token = create_account(
        session,
        init_key=payload.init_key,
        platform=payload.platform,
        app_version=payload.app_version,
        timezone=payload.timezone,
    )
    return ok_model(
        AccountInitResponse(
            access_token=token,
            account_id=account.public_id,
            created_at=account.created_at,
            platform=account.platform,
            is_new=True,
        ),
        message="账户已创建",
    )


@router.get("/me", summary="获取当前账户信息")
def me(account: CurrentAccount, session: SessionDep) -> dict:
    setting = get_setting(session, account)
    anchor = anchor_for(account, last_checkin_at(session, account.id))  # type: ignore[arg-type]
    return ok_model(
        {
            "account": AccountPublic(
                account_id=account.public_id,
                created_at=account.created_at,
                platform=account.platform,
                app_version=account.app_version,
                timezone=setting.timezone,
            ),
            "setting": build_setting_read(setting, anchor),
        }
    )
