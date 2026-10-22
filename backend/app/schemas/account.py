"""账户相关 DTO。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.base import CamelModel


class AccountInitRequest(CamelModel):
    # 客户端生成的幂等键；重复提交同一个 key 不会创建新账户
    init_key: str = Field(min_length=8, max_length=64)
    platform: str = Field(default="unknown", max_length=32)
    app_version: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("init_key")
    @classmethod
    def _clean_key(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 8:
            raise ValueError("initKey 长度至少 8 位")
        return cleaned


class AccountInitResponse(CamelModel):
    access_token: str
    account_id: str
    created_at: datetime
    platform: str
    is_new: bool


class AccountPublic(CamelModel):
    account_id: str
    created_at: datetime
    platform: str
    app_version: str | None = None
    timezone: str
