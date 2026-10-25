"""主键与对外标识的生成。

- ``uuid7()``：RFC 9562 UUIDv7，前 48 位是毫秒时间戳，按时间自然有序，
  适合做主键（比 UUIDv4 的随机分布更利于 B 树索引）。Python 3.13 尚未内置，
  这里自行实现，且在同一毫秒内用 12 位计数器保证单调递增。
- ``new_public_id()``：9 位纯数字（100000000-999999999），给用户看/报障时口述，
  唯一性由数据库唯一索引保证（见 ``account.public_id``）。
"""

from __future__ import annotations

import os
import secrets
import threading
import time
import uuid

# 9 位数字，首位不为 0，避免被当成"少一位"或丢前导零
PUBLIC_ID_MIN = 100_000_000
PUBLIC_ID_MAX = 999_999_999
PUBLIC_ID_LENGTH = 9

_LOCK = threading.Lock()
_last_ms = 0
_seq = 0
_SEQ_MAX = 0xFFF  # rand_a 共 12 位

_RAND_B_MASK = (1 << 62) - 1
_TS_MASK = (1 << 48) - 1


def uuid7() -> uuid.UUID:
    """生成 UUIDv7（时间有序）。"""
    global _last_ms, _seq

    with _LOCK:
        now_ms = int(time.time() * 1000)
        if now_ms > _last_ms:
            _last_ms = now_ms
            _seq = 0
        else:
            # 同一毫秒内递增；计数器用尽则借用下一毫秒，保证单调
            _seq += 1
            if _seq > _SEQ_MAX:
                _last_ms += 1
                _seq = 0
        ts_ms = _last_ms
        seq = _seq

    rand_b = int.from_bytes(os.urandom(8), "big") & _RAND_B_MASK

    value = (ts_ms & _TS_MASK) << 80
    value |= 0x7 << 76  # version = 7
    value |= seq << 64  # rand_a
    value |= 0b10 << 62  # variant = RFC 4122
    value |= rand_b
    return uuid.UUID(int=value)


def uuid7_timestamp_ms(value: uuid.UUID) -> int:
    """从 UUIDv7 里取出毫秒时间戳（用于排查）。"""
    return value.int >> 80


def new_public_id() -> str:
    """9 位数字对外标识。碰撞由唯一索引兜底，调用方需处理重试。"""
    return str(secrets.randbelow(PUBLIC_ID_MAX - PUBLIC_ID_MIN + 1) + PUBLIC_ID_MIN)


def is_valid_public_id(value: str) -> bool:
    return len(value) == PUBLIC_ID_LENGTH and value.isdigit() and value[0] != "0"
