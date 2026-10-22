"""后端定时任务入口。

- 单实例保护：PostgreSQL advisory lock（SQLite 直接跳过）
- 每个 tick：扫描到期账户 → 创建异常事件与通知任务 → 派发待发送邮件
- 任何异常都不会中断循环，只记录日志，下一轮继续
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime

from sqlalchemy import text
from sqlmodel import Session

from app.core.config import settings
from app.core.db import get_engine
from app.core.logging import get_logger
from app.services.alert_service import scan_once
from app.services.notification_service import dispatch_pending
from app.services.timeutil import now_utc

logger = get_logger(__name__)


def _try_lock(conn) -> bool:  # noqa: ANN001
    if conn.dialect.name != "postgresql":
        return True
    return bool(
        conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": settings.SCHEDULER_LOCK_KEY}).scalar()
    )


def _unlock(conn) -> None:  # noqa: ANN001
    if conn.dialect.name != "postgresql":
        return
    conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": settings.SCHEDULER_LOCK_KEY})


def run_once(now: datetime | None = None) -> dict:
    """同步执行一轮扫描 + 派发，返回统计信息。可被 API / 测试直接调用。"""
    moment = now or now_utc()
    engine = get_engine()
    with engine.connect() as conn:
        if not _try_lock(conn):
            logger.info("未获取到调度锁，跳过本轮（其他实例正在执行）")
            return {"skipped": True, "reason": "lock_not_acquired"}
        try:
            with Session(engine) as session:
                scan = scan_once(session, now=moment)
            with Session(engine) as session:
                dispatch = dispatch_pending(session, now=moment)
            logger.info("调度完成 scan=%s dispatch=%s", scan.as_dict(), dispatch.as_dict())
            return {"skipped": False, "scan": scan.as_dict(), "dispatch": dispatch.as_dict()}
        finally:
            _unlock(conn)


class SchedulerService:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="zaima-scheduler", daemon=True)
        self._thread.start()
        logger.info("调度器已启动，间隔 %s 秒", settings.SCHEDULER_INTERVAL_SECONDS)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("调度器已停止")

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                run_once()
                self.last_error = None
            except Exception as exc:  # noqa: BLE001 - 保持循环存活
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.exception("调度轮次失败")
            self._stop.wait(settings.SCHEDULER_INTERVAL_SECONDS)


scheduler = SchedulerService()


async def run_once_async(now: datetime | None = None) -> dict:
    """在事件循环中安全调用（避免阻塞）。"""
    return await asyncio.to_thread(run_once, now)
