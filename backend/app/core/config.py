"""应用配置：全部通过环境变量注入，禁止在代码里硬编码敏感信息。"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- 基础 ----------
    APP_NAME: str = "zaima-api"
    APP_ENV: Literal["dev", "test", "prod"] = "dev"
    DEBUG: bool = True
    API_PREFIX: str = "/api"
    DOCS_ENABLED: bool = True

    # ---------- 数据库 ----------
    DATABASE_URL: str = "postgresql+psycopg://zaima:zaima@127.0.0.1:55432/zaima"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False
    # 仅开发/测试环境允许自动建表；生产必须走 Alembic 迁移
    AUTO_CREATE_TABLES: bool = True

    # ---------- 跨域 ----------
    CORS_ORIGINS: str = "*"

    # ---------- 静态资源（一体化调试镜像使用）----------
    # 仅当 APP_ENV=dev 且该目录内存在 index.html 时，才由后端在同一端口托管前端页面。
    # 非 dev 环境即使设置了该变量也会被忽略（避免调试页面泄漏到线上）。
    STATIC_DIR: str = ""
    # 可选访问口令：留空表示不校验（默认）。设置后访问页面必须带 ?k=<口令>，
    # 校验通过会写入 Cookie。仅用于 dev 环境，属于「防随手打开」的挡板，不是安全边界。
    STATIC_ACCESS_KEY: str = ""
    # 品牌 Logo 链接（前端 favicon / 对外品牌展示使用）。
    # dev 一体化镜像会由后端在 /static/logo.svg 提供该文件；
    # 生产/独立 API 环境请改为可公开访问的绝对地址（如 CDN）。
    LOGO_URL: str = "/static/logo.svg"

    # ---------- 日志 ----------
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # ---------- 业务默认值 ----------
    DEFAULT_PERIOD_DAYS: int = 1
    DEFAULT_CHECKIN_TIME: str = "08:00"
    DEFAULT_TIMEZONE: str = "Asia/Shanghai"
    MAX_GUARDIANS: int = 3
    # 相对「应确认时间」的提醒偏移（分钟）：08:30 / 12:00 / 20:00
    REMINDER_OFFSETS_MINUTES: str = "30,240,720"
    # 相对「应确认时间」的异常事件偏移（分钟）：次日 08:00
    ALERT_OFFSET_MINUTES: int = 1440
    # 允许的确认周期（天）
    ALLOWED_PERIOD_DAYS: str = "1,2,3,7"
    # 同一 due 窗口内允许的确认客户端时间漂移（分钟），仅用于展示，不参与判定
    CHECKIN_HISTORY_DEFAULT_LIMIT: int = 20

    # ---------- 邮件 ----------
    EMAIL_ADAPTER: Literal["smtp", "mock"] = "mock"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@zaima.local"
    SMTP_FROM_NAME: str = "在吗"
    SMTP_USE_TLS: bool = True
    SMTP_TIMEOUT_SECONDS: int = 15
    EMAIL_MAX_ATTEMPTS: int = 3
    EMAIL_RETRY_BACKOFF_SECONDS: int = 60
    # 开发环境把邮件落盘，便于验证
    EMAIL_MOCK_DIR: str = "./.mailbox"

    # ---------- 调度 ----------
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_INTERVAL_SECONDS: int = 60
    SCHEDULER_BATCH_SIZE: int = 200
    SCHEDULER_LOCK_KEY: int = 918273645
    # 允许通过请求头模拟时间推进（仅 dev/test）
    ALLOW_TIME_TRAVEL: bool = True

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _strip_origins(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        raw = (self.CORS_ORIGINS or "").strip()
        if not raw or raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def reminder_offsets(self) -> list[int]:
        return sorted(
            int(item.strip())
            for item in self.REMINDER_OFFSETS_MINUTES.split(",")
            if item.strip() != ""
        )

    @property
    def allowed_period_days(self) -> list[int]:
        return sorted(
            int(item.strip())
            for item in self.ALLOWED_PERIOD_DAYS.split(",")
            if item.strip() != ""
        )

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV == "dev"

    def public_dict(self) -> dict[str, Any]:
        """用于启动日志，敏感字段脱敏。"""
        data = self.model_dump()
        for key in ("SMTP_PASSWORD", "DATABASE_URL"):
            if data.get(key):
                data[key] = "***"
        return json.loads(json.dumps(data, default=str))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
