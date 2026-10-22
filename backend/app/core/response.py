"""统一响应结构与全局异常处理。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)


def envelope(
    data: Any = None,
    *,
    code: str = str(ErrorCode.OK),
    message: str = "success",
    request_id: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data,
        "requestId": request_id or request_id_ctx.get(),
    }


def ok(data: Any = None, message: str = "success") -> dict[str, Any]:
    return envelope(data, code=str(ErrorCode.OK), message=message)


def serialize(data: Any) -> Any:
    """把 Pydantic 模型/列表统一转成 camelCase 的可 JSON 化结构。"""
    from pydantic import BaseModel

    if isinstance(data, BaseModel):
        return data.model_dump(mode="json", by_alias=True)
    if isinstance(data, list):
        return [serialize(item) for item in data]
    if isinstance(data, dict):
        return {key: serialize(value) for key, value in data.items()}
    return data


def ok_model(data: Any, message: str = "success") -> dict[str, Any]:
    return ok(serialize(data), message)


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: dict | None = None,
) -> JSONResponse:
    payload = envelope(None, code=code, message=message)
    if details:
        payload["details"] = details
    return JSONResponse(status_code=status_code, content=payload)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:  # noqa: ANN202
        if exc.status_code >= 500:
            logger.error("业务异常 %s: %s", exc.code, exc.message)
        else:
            logger.info("请求被拒绝 %s: %s", exc.code, exc.message)
        return error_response(exc.status_code, exc.code, exc.message, details=exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:  # noqa: ANN202
        details = {"errors": _simplify_errors(exc.errors())}
        return error_response(
            422,
            str(ErrorCode.VALIDATION_ERROR),
            "请求参数不合法",
            details=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:  # noqa: ANN202
        code = {
            401: ErrorCode.UNAUTHORIZED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            405: ErrorCode.BAD_REQUEST,
            429: ErrorCode.RATE_LIMITED,
        }.get(exc.status_code, ErrorCode.BAD_REQUEST)
        return error_response(exc.status_code, str(code), str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:  # noqa: ANN202
        logger.exception("未处理异常: %s", exc)
        return error_response(
            500,
            str(ErrorCode.INTERNAL_ERROR),
            "服务暂时不可用，请稍后重试",
        )


def _simplify_errors(errors: list[dict]) -> list[dict]:
    simplified = []
    for item in errors:
        simplified.append(
            {
                "loc": ".".join(str(part) for part in item.get("loc", [])),
                "msg": item.get("msg", ""),
                "type": item.get("type", ""),
            }
        )
    return simplified
