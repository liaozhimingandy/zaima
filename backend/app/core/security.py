"""匿名账户凭证的生成与校验。

凭证格式：``zm_<public_id>.<secret>``
- public_id：服务端生成的高熵随机串（用于定位账户）
- secret：服务端生成的高熵随机串（仅哈希入库，明文只返回一次）

日志中一律不打印完整凭证。
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

TOKEN_PREFIX = "zm_"
_PUBLIC_ID_BYTES = 12  # 96 bit
_SECRET_BYTES = 32  # 256 bit

_TOKEN_RE = re.compile(r"^zm_([A-Za-z0-9_-]{8,64})\.([A-Za-z0-9_-]{16,128})$")


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def new_public_id() -> str:
    return secrets.token_urlsafe(_PUBLIC_ID_BYTES).replace("-", "").replace("_", "")[:16]


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
