"""主键与对外标识的生成规则。"""

from __future__ import annotations

import time
import uuid

from app.core.ids import (
    PUBLIC_ID_LENGTH,
    PUBLIC_ID_MAX,
    PUBLIC_ID_MIN,
    is_valid_public_id,
    new_public_id,
    uuid7,
    uuid7_timestamp_ms,
)


def test_uuid7_has_correct_version_and_variant() -> None:
    value = uuid7()
    assert isinstance(value, uuid.UUID)
    assert value.version == 7
    assert value.variant == uuid.RFC_4122


def test_uuid7_is_time_ordered() -> None:
    """同一进程内连续生成必须严格递增（内含毫秒级计数器）。"""
    values = [uuid7() for _ in range(2000)]
    assert values == sorted(values)
    assert len({v.int for v in values}) == len(values)


def test_uuid7_embeds_current_timestamp() -> None:
    before = int(time.time() * 1000)
    value = uuid7()
    after = int(time.time() * 1000)
    assert before - 5 <= uuid7_timestamp_ms(value) <= after + 5


def test_public_id_is_nine_digits() -> None:
    for _ in range(500):
        value = new_public_id()
        assert len(value) == PUBLIC_ID_LENGTH
        assert value.isdigit()
        assert value[0] != "0"
        assert PUBLIC_ID_MIN <= int(value) <= PUBLIC_ID_MAX
        assert is_valid_public_id(value)


def test_public_id_rejects_bad_values() -> None:
    for bad in ("", "12345678", "1234567890", "012345678", "12345678a"):
        assert not is_valid_public_id(bad)


def test_public_id_space_is_large_enough() -> None:
    """9 位数有 9 亿个取值；抽 20000 个不应出现明显碰撞。"""
    values = {new_public_id() for _ in range(20000)}
    assert len(values) > 19990
