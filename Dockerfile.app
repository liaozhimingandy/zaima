# 在吗 · 一体化调试镜像（API + H5 同源）
#
# 用途：一条 docker run 就能在浏览器打开 H5 并直接排查问题。
#      前端由后端在同一端口托管（STATIC_DIR），不需要 CORS、不需要额外 Nginx。
#
# 构建（上下文必须是仓库根目录）：
#   docker build -f Dockerfile.app -t zaima-app:local .
#
# 运行：
#   docker run --rm -p 8080:8000 zaima-app:local
#   # 浏览器打开 http://127.0.0.1:8080/
#
# 注意：本镜像默认 APP_ENV=dev + SQLite + 模拟邮件，仅用于调试/演示，不可用于生产。
# 生产只部署 backend/Dockerfile 的纯 API 镜像（不含前端，体积约 81MB）。
# 页面托管有三层限制（见 backend/app/main.py::resolve_static_root）：
#   1. 只有 APP_ENV=dev 才托管；改成 prod 后 / 只返回 JSON，静态资源全 404
#   2. 只暴露 / 与 /assets/*，不挂载整目录、不开目录列表
#   3. 运行时请把端口绑到回环：-p 127.0.0.1:8098:8000

ARG NODE_IMAGE=node:22-slim
ARG PYTHON_IMAGE=python:3.13-alpine

# ---------------- 1. 构建 H5 ----------------
FROM ${NODE_IMAGE} AS web

# 让「我的」页面显示的版本号与镜像版本一致，排查时能确认看到的是哪个构建
ARG APP_VERSION=dev

WORKDIR /web

# 先装依赖，利用层缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry=https://registry.npmjs.org --no-audit --no-fund

COPY frontend/ ./

# API 基址置为 "/"：构建后 API_BASE_URL 为空串，前端请求走同源 /api，
# 换端口、换域名都不用重新构建。
ENV VITE_API_BASE_URL=/ \
    VITE_APP_VERSION=${APP_VERSION}
RUN npm run build:h5 && test -f dist/build/h5/index.html

# ---------------- 2. Python 依赖 ----------------
FROM ${PYTHON_IMAGE} AS deps

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY backend/requirements.txt ./

RUN set -eux; \
    python -m venv /opt/venv; \
    /opt/venv/bin/pip install --no-cache-dir --no-compile -r requirements.txt; \
    # 运行期不需要构建/安装工具
    /opt/venv/bin/pip uninstall -y pip setuptools wheel >/dev/null 2>&1 || true; \
    rm -rf /opt/venv/lib/python3*/site-packages/pip* \
           /opt/venv/lib/python3*/site-packages/setuptools* \
           /opt/venv/lib/python3*/site-packages/pkg_resources \
           /opt/venv/lib/python3*/site-packages/wheel*; \
    find /opt/venv -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true; \
    find /opt/venv -name '*.pyc' -delete 2>/dev/null || true

# ---------------- 3. 运行镜像 ----------------
FROM ${PYTHON_IMAGE} AS runtime

ARG APP_VERSION=dev
ARG VCS_REF=unknown

LABEL org.opencontainers.image.title="zaima-app-debug" \
      org.opencontainers.image.description="Zaima all-in-one DEBUG image (API + H5, SQLite, mock email) - not for production" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.licenses="MIT"

# 调试镜像的默认值：开箱即用（生产镜像见 backend/Dockerfile）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    TZ=UTC \
    APP_ENV=dev \
    AUTO_CREATE_TABLES=true \
    RUN_MIGRATIONS=false \
    DATABASE_URL=sqlite+pysqlite:////data/zaima.db \
    EMAIL_ADAPTER=mock \
    EMAIL_MOCK_DIR=/data/mailbox \
    ALLOW_TIME_TRAVEL=true \
    SCHEDULER_ENABLED=true \
    SCHEDULER_INTERVAL_SECONDS=60 \
    STATIC_DIR=/app/static \
    CORS_ORIGINS=*

RUN addgroup -g 10001 -S app \
    && adduser -u 10001 -S -G app -h /app -s /sbin/nologin app \
    && mkdir -p /data/mailbox /app/static \
    && chown -R app:app /data /app

WORKDIR /app

COPY --from=deps /opt/venv /opt/venv
COPY backend/docker-entrypoint.sh ./
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY --from=web /web/dist/build/h5 ./static

RUN chmod +x ./docker-entrypoint.sh && chown -R app:app /app

USER app

# SQLite 与模拟邮件落盘的持久化目录
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=6 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

STOPSIGNAL SIGTERM

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--timeout-graceful-shutdown", "20"]
