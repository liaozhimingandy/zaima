"""守护人服务。"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.errors import ConflictError, ErrorCode, NotFoundError
from app.core.logging import get_logger
from app.models import Account, Guardian
from app.schemas.guardian import GuardianCreate, GuardianListResponse, GuardianRead, GuardianUpdate

logger = get_logger(__name__)


def _to_read(guardian: Guardian) -> GuardianRead:
    return GuardianRead(
        id=guardian.id,  # type: ignore[arg-type]
        name=guardian.name,
        email=guardian.email,
        relation=guardian.relation,
        created_at=guardian.created_at,
    )


def list_guardians(session: Session, account: Account) -> GuardianListResponse:
    rows = list(
        session.exec(
            select(Guardian)
            .where(Guardian.account_id == account.id)
            .order_by(Guardian.sort_order, Guardian.id)  # type: ignore[attr-defined]
        ).all()
    )
    return GuardianListResponse(
        items=[_to_read(item) for item in rows],
        max_count=settings.MAX_GUARDIANS,
        remaining=max(settings.MAX_GUARDIANS - len(rows), 0),
    )


def get_owned(session: Session, account: Account, guardian_id: int) -> Guardian:
    guardian = session.exec(
        select(Guardian).where(
            Guardian.id == guardian_id,
            Guardian.account_id == account.id,
        )
    ).first()
    if guardian is None:
        # 不区分「不存在」与「属于其他账户」，避免越权探测
        raise NotFoundError("守护人不存在")
    return guardian


def create_guardian(session: Session, account: Account, payload: GuardianCreate) -> GuardianRead:
    current = list(
        session.exec(select(Guardian).where(Guardian.account_id == account.id)).all()
    )
    if len(current) >= settings.MAX_GUARDIANS:
        raise ConflictError(
            f"最多只能添加 {settings.MAX_GUARDIANS} 位守护人",
            code=ErrorCode.GUARDIAN_LIMIT,
        )

    email = str(payload.email).lower()
    if any(item.email == email for item in current):
        raise ConflictError("该邮箱已在守护人列表中", code=ErrorCode.GUARDIAN_EMAIL_DUPLICATE)

    guardian = Guardian(
        account_id=account.id,
        name=payload.name,
        email=email,
        relation=payload.relation,
        sort_order=len(current),
    )
    session.add(guardian)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            "该邮箱已在守护人列表中", code=ErrorCode.GUARDIAN_EMAIL_DUPLICATE
        ) from exc
    session.refresh(guardian)
    logger.info("新增守护人 account_id=%s guardian_id=%s", account.public_id, guardian.id)
    return _to_read(guardian)


def update_guardian(
    session: Session, account: Account, guardian_id: int, payload: GuardianUpdate
) -> GuardianRead:
    guardian = get_owned(session, account, guardian_id)
    if payload.name is not None:
        guardian.name = payload.name
    if payload.relation is not None:
        guardian.relation = payload.relation
    if payload.email is not None:
        email = str(payload.email).lower()
        if email != guardian.email:
            conflict = session.exec(
                select(Guardian).where(
                    Guardian.account_id == account.id,
                    Guardian.email == email,
                    Guardian.id != guardian.id,
                )
            ).first()
            if conflict is not None:
                raise ConflictError(
                    "该邮箱已在守护人列表中", code=ErrorCode.GUARDIAN_EMAIL_DUPLICATE
                )
            guardian.email = email

    session.add(guardian)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            "该邮箱已在守护人列表中", code=ErrorCode.GUARDIAN_EMAIL_DUPLICATE
        ) from exc
    session.refresh(guardian)
    logger.info("更新守护人 account_id=%s guardian_id=%s", account.public_id, guardian.id)
    return _to_read(guardian)


def delete_guardian(session: Session, account: Account, guardian_id: int) -> None:
    guardian = get_owned(session, account, guardian_id)
    session.delete(guardian)
    session.commit()
    logger.info("删除守护人 account_id=%s guardian_id=%s", account.public_id, guardian_id)
