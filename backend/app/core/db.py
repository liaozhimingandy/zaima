"""数据库连接与 Session 管理。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_engine: Engine | None = None


def _engine_kwargs(url: str) -> dict:
    kwargs: dict = {"echo": settings.DB_ECHO, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        return kwargs
    kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
    )
    return kwargs


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = settings.DATABASE_URL
        logger.info("初始化数据库引擎", extra={"driver": url.split("://")[0]})
        _engine = create_engine(url, **_engine_kwargs(url))
    return _engine


def set_engine(engine: Engine | None) -> None:
    """测试用：注入自定义引擎。"""
    global _engine
    _engine = engine


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """显式事务边界：正常提交，异常回滚。"""
    session = Session(get_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """开发/测试环境自动建表。生产环境必须使用 Alembic。"""
    # 触发模型注册
    import app.models  # noqa: F401

    if settings.AUTO_CREATE_TABLES:
        SQLModel.metadata.create_all(get_engine())
        logger.info("已确保表结构存在（AUTO_CREATE_TABLES=true）")


def check_db() -> tuple[bool, str | None]:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # pragma: no cover - 依赖真实数据库状态
        return False, str(exc)
