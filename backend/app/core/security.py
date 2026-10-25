"""匿名账户凭证的生成与校验。

凭证格式：``zm_<9位数字 public_id>.<secret>``
- public_id：9 位纯数字，方便用户口述/报障，唯一性由数据库唯一索引保证
- secret：服务端生成的高熵随机串（仅哈希入库，明文只返回一次）

日志中一律不打印完整凭证。
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from app.core.ids import PUBLIC_ID_LENGTH, new_public_id  # noqa: F401  对外复用

TOKEN_PREFIX = "zm_"
_SECRET_BYTES = 32  # 256 bit

# public_id 固定 9 位数字；secret 为 urlsafe base64
_TOKEN_RE = re.compile(
    rf"^zm_(\d{{{PUBLIC_ID_LENGTH}}})\.([A-Za-z0-9_-]{{16,128}})$"
)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def new_secret() -> str:
    return secrets.token_urlsafe(_SECRET_BYTES)


def build_token(public_id: str, secret: str) -> str:
    return f"{TOKEN_PREFIX}{public_id}.{secret}"


def parse_token(token: str | None) -> tuple[str, str] | None:
    if not token:
        return None
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    match = _TOKEN_RE.match(token)
    if not match:
        return None
    return match.group(1), match.group(2)


def verify_secret(secret: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(secret), stored_hash)


def mask_token(token: str | None) -> str:
    """用于日志/调试的脱敏展示。"""
    parsed = parse_token(token)
    if not parsed:
        return "***"
    public_id, secret = parsed
    return f"{TOKEN_PREFIX}{public_id}.{secret[:4]}***"
