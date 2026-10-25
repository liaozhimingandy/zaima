"""FastAPI 应用入口。"""

from __future__ import annotations

import hmac
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app import __version__
from app.api.routes import account as account_routes
from app.api.routes import checkin as checkin_routes
from app.api.routes import dev as dev_routes
from app.api.routes import guardians as guardian_routes
from app.api.routes import health as health_routes
from app.core.config import settings
from app.core.db import init_db
from app.core.logging import get_logger, new_request_id, request_id_ctx, setup_logging
from app.core.response import register_exception_handlers
from app.scheduler import scheduler

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("服务启动 env=%s version=%s", settings.APP_ENV, __version__)
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001 - 数据库不可用时仍提供健康检查
        logger.error("数据库初始化失败：%s", exc)
    # 模拟邮件目录在启动时建好，避免"发第一封邮件前目录不存在"造成的排查困惑
    if settings.EMAIL_ADAPTER == "mock":
        try:
            Path(settings.EMAIL_MOCK_DIR).expanduser().mkdir(parents=True, exist_ok=True)
            logger.info("模拟邮件目录：%s", settings.EMAIL_MOCK_DIR)
        except OSError as exc:
            logger.warning("无法创建模拟邮件目录 %s：%s", settings.EMAIL_MOCK_DIR, exc)
    if settings.SCHEDULER_ENABLED:
        scheduler.start()
    else:
        logger.warning("调度器已禁用（SCHEDULER_ENABLED=false）")
    try:
        yield
    finally:
        scheduler.stop()
        logger.info("服务已停止")


app = FastAPI(
    title="在吗 · API",
    description="每天点一下，让有人知道你还在。V1 匿名账户 + 定期确认 + 守护人邮件提醒。",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.DOCS_ENABLED else None,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # 使用 Bearer 凭证，不依赖 Cookie
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):  # noqa: ANN001, ANN201
    request_id = request.headers.get("X-Request-ID") or new_request_id()
    token = request_id_ctx.set(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = int((time.perf_counter() - started) * 1000)
        logger.exception("请求处理异常 %s %s (%sms)", request.method, request.url.path, elapsed)
        request_id_ctx.reset(token)
        raise
    elapsed = int((time.perf_counter() - started) * 1000)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = str(elapsed)
    if request.url.path not in ("/docs", "/openapi.json", "/redoc"):
        logger.info(
            "%s %s -> %s (%sms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
    request_id_ctx.reset(token)
    return response


app.include_router(health_routes.router, prefix=settings.API_PREFIX)
app.include_router(account_routes.router, prefix=settings.API_PREFIX)
app.include_router(checkin_routes.router, prefix=settings.API_PREFIX)
app.include_router(guardian_routes.router, prefix=settings.API_PREFIX)

if not settings.is_prod:
    app.include_router(dev_routes.router, prefix=settings.API_PREFIX)
    logger.info("已启用开发调试接口 /api/dev/*")


def resolve_static_root() -> Path | None:
    """决定是否托管前端页面，返回静态根目录或 None。

    安全约束（防止有人直接打开网页）：
    - **只有 APP_ENV=dev 才允许**，其它环境即使配置了 STATIC_DIR 也一律忽略
    - 目录内必须存在 index.html
    """
    if not settings.STATIC_DIR:
        return None
    if not settings.is_dev:
        logger.warning(
            "STATIC_DIR=%s 已配置，但 APP_ENV=%s，出于安全考虑不托管前端页面（仅 dev 允许）",
            settings.STATIC_DIR,
            settings.APP_ENV,
        )
        return None
    root = Path(settings.STATIC_DIR).expanduser().resolve()
    if not (root / "index.html").is_file():
        logger.warning("STATIC_DIR=%s 未找到 index.html，跳过静态托管", settings.STATIC_DIR)
        return None
    return root


STATIC_COOKIE = "zm_dev_access"


def static_access_ok(provided: str | None, cookie: str | None) -> bool:
    """校验页面访问口令。未配置口令时一律放行（默认行为）。"""
    expected = settings.STATIC_ACCESS_KEY
    if not expected:
        return True
    for candidate in (provided, cookie):
        if candidate and hmac.compare_digest(candidate, expected):
            return True
    return False


_LOCKED_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>在吗</title></head>
<body style="font-family:-apple-system,'PingFang SC',sans-serif;padding:48px 24px;color:#14171c;background:#f4f5f7;">
<h2 style="font-size:18px;">需要访问口令</h2>
<p style="color:#5b6270;font-size:14px;line-height:1.8;">
该页面只在开发环境提供，且需要访问口令。<br/>
请使用 <code>/?k=&lt;口令&gt;</code> 打开，或确认 <code>STATIC_ACCESS_KEY</code> 配置是否正确。
</p>
</body></html>"""


def _mount_static() -> bool:
    """同源托管 H5：只暴露首页 `/` 与 `/assets/*`，其余路径一律 404。

    不挂载整目录、不开启目录列表，避免静态目录被逐个探测。
    """
    root = resolve_static_root()
    if root is None:
        return False

    assets_root = (root / "assets").resolve()

    @app.get("/", include_in_schema=False, response_class=HTMLResponse)
    def spa_index(request: Request, k: str | None = Query(default=None, max_length=128)):  # noqa: ANN202
        if not static_access_ok(k, request.cookies.get(STATIC_COOKIE)):
            return HTMLResponse(_LOCKED_PAGE, status_code=401)
        if k:
            # 校验通过后写入 Cookie 并跳回干净 URL，避免口令留在地址栏/历史记录
            response = RedirectResponse(url="/", status_code=307)
            response.set_cookie(
                STATIC_COOKIE,
                k,
                max_age=86400,
                httponly=True,
                samesite="lax",
                path="/",
            )
            return response
        return FileResponse(
            root / "index.html",
            media_type="text/html; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            },
        )

    @app.get("/assets/{asset_path:path}", include_in_schema=False)
    def spa_asset(asset_path: str, request: Request):  # noqa: ANN202
        if not static_access_ok(None, request.cookies.get(STATIC_COOKIE)):
            raise HTTPException(status_code=401, detail="需要访问口令")
        target = (assets_root / asset_path).resolve()
        if not target.is_relative_to(assets_root) or not target.is_file():
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(target)

    # 公开的静态资源（logo 等）：与 /assets/* 类似，但面向公开访问，不校验口令。
    # 仅 dev 提供；做路径穿越防护，只允许读取 STATIC_DIR/static 下的真实文件。
    static_root = (root / "static").resolve()

    @app.get("/static/{path:path}", include_in_schema=False)
    def spa_static(path: str, request: Request):  # noqa: ANN202
        target = (static_root / path).resolve()
        if not target.is_relative_to(static_root) or not target.is_file():
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(target)

    logger.info(
        "已在 dev 环境托管前端页面：%s（仅 / 与 /assets/* 可访问%s）",
        root,
        "，已启用访问口令" if settings.STATIC_ACCESS_KEY else "",
    )
    return True


_has_static = _mount_static()

if not _has_static:

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "name": "在吗 API",
            "version": __version__,
            "docs": "/docs" if settings.DOCS_ENABLED else None,
            "slogan": "每天点一下，让有人知道你还在。",
            "logo": settings.LOGO_URL,
            "hint": "当前未托管前端页面：前端仅在 APP_ENV=dev 且设置 STATIC_DIR 时可用",
        }
