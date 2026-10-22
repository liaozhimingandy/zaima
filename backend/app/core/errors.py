"""业务异常与统一错误码。"""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    OK = "OK"
    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    ACCOUNT_EXISTS = "ACCOUNT_EXISTS"
    GUARDIAN_LIMIT = "GUARDIAN_LIMIT"
    GUARDIAN_EMAIL_DUPLICATE = "GUARDIAN_EMAIL_DUPLICATE"
    DUPLICATE_CHECKIN = "DUPLICATE_CHECKIN"
    EMAIL_NOT_CONFIGURED = "EMAIL_NOT_CONFIGURED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(Exception):
    """可预期的业务异常，直接映射为统一响应结构。"""

    def __init__(
        self,
        code: ErrorCode | str,
        message: str,
        *,
        status_code: int = 400,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, message: str = "资源不存在", details: dict | None = None) -> None:
        super().__init__(ErrorCode.NOT_FOUND, message, status_code=404, details=details)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "账户凭证无效或已失效") -> None:
        super().__init__(ErrorCode.UNAUTHORIZED, message, status_code=401)


class ConflictError(AppError):
    def __init__(
        self, message: str, code: ErrorCode | str = ErrorCode.CONFLICT, details: dict | None = None
    ) -> None:
        super().__init__(code, message, status_code=409, details=details)


class ValidationError(AppError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(ErrorCode.VALIDATION_ERROR, message, status_code=422, details=details)
