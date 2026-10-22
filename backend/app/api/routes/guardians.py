"""守护人接口。"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentAccount, SessionDep
from app.core.response import ok_model
from app.schemas.guardian import GuardianCreate, GuardianUpdate
from app.services.guardian_service import (
    create_guardian,
    delete_guardian,
    list_guardians,
    update_guardian,
)

router = APIRouter(prefix="/guardians", tags=["guardians"])


@router.get("", summary="守护人列表")
def read_guardians(account: CurrentAccount, session: SessionDep) -> dict:
    return ok_model(list_guardians(session, account))


@router.post("", status_code=status.HTTP_201_CREATED, summary="添加守护人")
def add_guardian(payload: GuardianCreate, account: CurrentAccount, session: SessionDep) -> dict:
    guardian = create_guardian(session, account, payload)
    return ok_model(guardian, message="守护人已添加")


@router.put("/{guardian_id}", summary="编辑守护人")
def edit_guardian(
    guardian_id: int,
    payload: GuardianUpdate,
    account: CurrentAccount,
    session: SessionDep,
) -> dict:
    guardian = update_guardian(session, account, guardian_id, payload)
    return ok_model(guardian, message="守护人已更新")


@router.delete("/{guardian_id}", summary="删除守护人")
def remove_guardian(guardian_id: int, account: CurrentAccount, session: SessionDep) -> dict:
    delete_guardian(session, account, guardian_id)
    return ok_model({"deleted": True, "id": guardian_id}, message="守护人已删除")
