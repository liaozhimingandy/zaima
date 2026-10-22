"""守护人 DTO。"""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.schemas.base import CamelModel


class GuardianRead(CamelModel):
    id: int
    name: str
    email: str
    relation: str | None
    created_at: datetime


class GuardianCreate(CamelModel):
    name: str = Field(min_length=1, max_length=32)
    email: EmailStr
    relation: str | None = Field(default=None, max_length=16)

    @field_validator("name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("姓名不能为空")
        return cleaned

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return value.strip().lower()


class GuardianUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=32)
    email: EmailStr | None = None
    relation: str | None = Field(default=None, max_length=16)

    @field_validator("name")
    @classmethod
    def _trim_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("姓名不能为空")
        return cleaned

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()


class GuardianListResponse(CamelModel):
    items: list[GuardianRead]
    max_count: int
    remaining: int
