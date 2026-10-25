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


_PUBLIC_ID_RETRIES = 8


def _allocate_public_id(session: Session) -> str:
    """分配一个未被占用的 9 位数字编号。

    先查一遍降低碰撞概率；真正的唯一性由 ``ix_account_public_id`` 唯一索引保证，
    极端并发下由调用方捕获 IntegrityError 重试。
    """
    for _ in range(_PUBLIC_ID_RETRIES):
        candidate = new_public_id()
        exists = session.exec(select(Account.id).where(Account.public_id == candidate)).first()
        if exists is None:
            return candidate
    raise RuntimeError("无法分配唯一的 9 位账户编号，请稍后重试")


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

    account: Account | None = None
    public_id = ""
    secret = ""

    for attempt in range(_PUBLIC_ID_RETRIES):
        public_id = _allocate_public_id(session)
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
            break
        except IntegrityError as exc:
            session.rollback()
            detail = str(getattr(exc, "orig", exc)).lower()
            # 9 位编号撞上了：换一个重试；其它冲突（init_key）走 409
            if "public_id" in detail and attempt < _PUBLIC_ID_RETRIES - 1:
                logger.warning("账户编号碰撞，重试第 %s 次", attempt + 1)
                account = None
                continue
            logger.warning("并发初始化冲突，已回滚：%s", type(exc).__name__)
            raise ConflictError(
                "该初始化请求已创建过账户，请使用本地保存的凭证",
                code=ErrorCode.ACCOUNT_EXISTS,
            ) from exc

    if account is None:
        raise ConflictError("账户创建失败，请稍后重试")

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
