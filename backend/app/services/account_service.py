"""匿名账户服务。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.errors import ConflictError, ErrorCode, UnauthorizedError
from app.core.logging import get_logger
from app.core.security import (
    build_token,
    hash_secret,
    new_public_id,
    new_secret,
    parse_token,
    verify_secret,
)
from app.models import Account
from app.models.enums import AccountStatus
from app.services.setting_service import ensure_setting

logger = get_logger(__name__)


def create_account(
    session: Session,
    *,
    init_key: str,
    platform: str,
    app_version: str | None,
    timezone: str | None,
) -> tuple[Account, str]:
    """创建匿名账户，返回 (account, access_token)。

    重复/并发初始化：``init_key`` 上的唯一索引保证只会落一条记录，
    冲突时返回 409 ``ACCOUNT_EXISTS``，由客户端决定复用本地凭证还是换 key 重试。
    """
    existing = session.exec(select(Account).where(Account.init_key == init_key)).first()
    if existing is not None:
        raise ConflictError(
            "该初始化请求已创建过账户，请使用本地保存的凭证",
            code=ErrorCode.ACCOUNT_EXISTS,
        )

    public_id = new_public_id()
    secret = new_secret()
    account = Account(
        public_id=public_id,
        secret_hash=hash_secret(secret),
        init_key=init_key,
        platform=platform or "unknown",
        app_version=app_version,
        status=AccountStatus.ACTIVE.value,
    )
    session.add(account)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        logger.warning("并发初始化冲突，已回滚：%s", type(exc).__name__)
        raise ConflictError(
            "该初始化请求已创建过账户，请使用本地保存的凭证",
            code=ErrorCode.ACCOUNT_EXISTS,
        ) from exc

    session.refresh(account)
    ensure_setting(session, account, timezone=timezone)
    logger.info("创建匿名账户 account_id=%s platform=%s", account.public_id, account.platform)
    return account, build_token(public_id, secret)


def authenticate(session: Session, token: str | None) -> Account:
    """根据 Bearer 凭证定位账户；失败一律 401，不区分具体原因。"""
    parsed = parse_token(token)
    if parsed is None:
        raise UnauthorizedError("缺少或格式非法的访问凭证")
    public_id, secret = parsed
    account = session.exec(select(Account).where(Account.public_id == public_id)).first()
    if account is None or not verify_secret(secret, account.secret_hash):
        raise UnauthorizedError()
    if account.status != AccountStatus.ACTIVE.value:
        raise UnauthorizedError("账户已停用")
    return account


def account_created_at(account: Account) -> datetime:
    return account.created_at
