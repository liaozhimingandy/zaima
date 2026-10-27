# 在吗 · API 服务端镜像（**不含任何前端文件**）
#
# 目标：只跑 HTTP API，体积尽量小。前端 H5 由 Nginx/CDN 或独立的调试镜像负责。
# 需要「容器启动就能看页面」的调试镜像请用仓库根目录的 Dockerfile.app。
#
# 构建（上下文是 backend/）：
#   docker build -f backend/Dockerfile -t zaima-api:local backend
#
# 体积优化手段：
#   1. alpine 基础镜像（musl），比 slim 小 ~45MB
#   2. 运行依赖只装 uvicorn 核心 + httptools，不装 uvloop/watchfiles/websockets/pyyaml
#   3. pip 安装用 --no-compile，不产生 __pycache__
#   4. 装完就卸载 pip/setuptools/wheel（运行期不需要）
#   5. 多阶段：运行镜像里没有任何构建工具

ARG PYTHON_IMAGE=python:3.13-alpine

# ---------- 依赖阶段 ----------
FROM ${PYTHON_IMAGE} AS deps

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt ./

RUN set -eux; \
    python -m venv /opt/venv; \
    /opt/venv/bin/pip install --no-cache-dir --no-compile -r requirements.txt; \
    # 运行期不需要构建/安装工具，卸掉可省 ~13MB
    /opt/venv/bin/pip uninstall -y pip setuptools wheel >/dev/null 2>&1 || true; \
    rm -rf /opt/venv/lib/python3*/site-packages/pip* \
           /opt/venv/lib/python3*/site-packages/setuptools* \
           /opt/venv/lib/python3*/site-packages/pkg_resources \
           /opt/venv/lib/python3*/site-packages/wheel*; \
    find /opt/venv -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true; \
    find /opt/venv -name '*.pyc' -delete 2>/dev/null || true

# ---------- 运行镜像 ----------
FROM ${PYTHON_IMAGE} AS runtime

ARG APP_VERSION=dev
ARG VCS_REF=unknown
# 构建号（CI 传提交短哈希），运行期由应用读取用于排查
ARG APP_BUILD=dev

LABEL org.opencontainers.image.title="zaima-api" \
      org.opencontainers.image.description="Zaima API - daily safety check-in service (no frontend)" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.licenses="MIT"

# 安全默认：镜像内不预置任何环境专属配置，
# 生产必须由部署阶段注入 DATABASE_URL / SMTP_* 等变量。
# APP_ENV=prod 保证即使忘记设置也不会暴露 /api/dev/* 调试接口。
# 注意：本镜像**不设置** STATIC_DIR，也不包含静态资源。
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    TZ=UTC \
    APP_ENV=prod \
    AUTO_CREATE_TABLES=false \
    RUN_MIGRATIONS=false \
    APP_VERSION="${APP_VERSION}" \
    APP_BUILD="${APP_BUILD}"

RUN addgroup -g 10001 -S app \
    && adduser -u 10001 -S -G app -h /app -s /sbin/nologin app

WORKDIR /app

COPY --from=deps /opt/venv /opt/venv
COPY docker-entrypoint.sh ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN chmod +x ./docker-entrypoint.sh \
    && chown -R app:app /app

USER app

EXPOSE 8000

# 使用应用自身的健康检查接口，容器编排可据此判断就绪
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

# 使用 exec 形式的入口脚本，SIGTERM 会传递给 uvicorn，实现优雅退出
STOPSIGNAL SIGTERM

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--timeout-graceful-shutdown", "20"]
