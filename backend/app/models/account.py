"""匿名账户模型。"""

from __future__ import annotations

from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin
from app.models.enums import AccountStatus


class Account(TimestampMixin, SQLModel, table=True):
    """匿名账户。

    - ``public_id`` 与 ``secret_hash`` 构成访问凭证，明文 secret 只返回给客户端一次
    - ``init_key`` 由客户端生成，用于初始化幂等（重复/并发初始化不会产生多个账户）
    """

    __tablename__ = "account"

    id: int | None = Field(default=None, primary_key=True)
    public_id: str = Field(max_length=32, unique=True, index=True, nullable=False)
    secret_hash: str = Field(max_length=64, nullable=False)
    init_key: str | None = Field(default=None, max_length=64, unique=True, index=True)
    platform: str = Field(default="unknown", max_length=32)
    app_version: str | None = Field(default=None, max_length=32)
    status: str = Field(default=AccountStatus.ACTIVE.value, max_length=16)
