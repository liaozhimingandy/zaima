"""匿名账户模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, Uuid
from sqlmodel import Field, SQLModel

from app.core.ids import PUBLIC_ID_LENGTH, uuid7
from app.models.base import created_at_column, updated_at_column
from app.models.enums import AccountStatus


class Account(SQLModel, table=True):
    """匿名账户。

    - 主键 ``id`` 为 UUIDv7（时间有序），不对外暴露，也不可被枚举
    - ``public_id`` 为 9 位数字，用于凭证定位与人工核对（客服/报障时口述）
    - ``public_id`` 与 ``secret_hash`` 构成访问凭证，明文 secret 只返回给客户端一次
    - ``init_key`` 由客户端生成，用于初始化幂等（重复/并发初始化不会产生多个账户）
    """

    __tablename__ = "account"

    id: uuid.UUID = Field(
        default_factory=uuid7,
        sa_column=Column(Uuid(as_uuid=True), primary_key=True, nullable=False),
    )
    public_id: str = Field(
        max_length=PUBLIC_ID_LENGTH, unique=True, index=True, nullable=False
    )
    secret_hash: str = Field(max_length=64, nullable=False)
    init_key: str | None = Field(default=None, max_length=64, unique=True, index=True)
    platform: str = Field(default="unknown", max_length=32)
    app_version: str | None = Field(default=None, max_length=32)
    status: str = Field(default=AccountStatus.ACTIVE.value, max_length=16)

    # 时间字段统一置于表末：创建时间、更新时间
    created_at: datetime = created_at_column()
    updated_at: datetime = updated_at_column()
