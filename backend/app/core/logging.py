"""结构化日志 + 请求追踪上下文。"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from typing import Any

from app.core.config import settings

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_RESERVED = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "requestId": getattr(record, "request_id", "-"),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.request_id = getattr(record, "request_id", "-")
        return (
            f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')} "
            f"[{record.levelname:<5}] [{record.request_id}] "
            f"{record.name}: {record.getMessage()}"
            + (f" | {record.exc_text}" if record.exc_text else "")
        )


def setup_logging() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ContextFilter())
    handler.setFormatter(JsonFormatter() if settings.LOG_JSON else PlainFormatter())
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL.upper())

    # 降低第三方库噪音
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DB_ECHO else logging.WARNING
    )


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class Timer:
    """简单耗时统计。"""

    def __init__(self) -> None:
        self.start = time.perf_counter()

    @property
    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self.start) * 1000)
