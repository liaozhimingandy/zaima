"""独立调度进程。

多副本部署时的推荐形态：API 容器设 ``SCHEDULER_ENABLED=false``，
只让一个独立 worker 容器执行扫描与派发（advisory lock 仍作为兜底）。

启动：``python -m app.worker``
"""

from __future__ import annotations

import signal
import threading
import time

from app.core.config import settings
from app.core.db import init_db
from app.core.logging import get_logger, setup_logging
from app.scheduler import run_once

logger = get_logger("app.worker")

_stop = threading.Event()


def _handle_signal(signum: int, _frame) -> None:  # noqa: ANN001
    logger.info("收到信号 %s，准备退出", signum)
    _stop.set()


def main() -> None:
    setup_logging()
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        init_db()
    except Exception as exc:  # noqa: BLE001
        logger.error("数据库初始化失败：%s", exc)

    interval = max(settings.SCHEDULER_INTERVAL_SECONDS, 5)
    logger.info("调度 worker 启动，间隔 %s 秒", interval)

    while not _stop.is_set():
        started = time.perf_counter()
        try:
            result = run_once()
            logger.info(
                "本轮完成 skipped=%s 耗时 %.2fs",
                result.get("skipped"),
                time.perf_counter() - started,
            )
        except Exception:  # noqa: BLE001 - 保持循环存活
            logger.exception("本轮调度失败")
        _stop.wait(interval)

    logger.info("调度 worker 已退出")


if __name__ == "__main__":
    main()
