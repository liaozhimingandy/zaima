"""Pydantic DTO（对外统一 camelCase）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    head, *rest = value.split("_")
    return head + "".join(word.capitalize() for word in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
