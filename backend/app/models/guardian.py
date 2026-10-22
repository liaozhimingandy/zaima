"""守护人模型。"""

from __future__ import annotations

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin


class Guardian(TimestampMixin, SQLModel, table=True):
    """守护人：只需要邮箱，不需要注册账户。"""

    __tablename__ = "guardian"
    __table_args__ = (
        UniqueConstraint("account_id", "email", name="uq_guardian_account_email"),
    )

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True, nullable=False)
    name: str = Field(max_length=32, nullable=False)
    email: str = Field(max_length=254, nullable=False, index=True)
    relation: str | None = Field(default=None, max_length=16)
    sort_order: int = Field(default=0, nullable=False)
