# =============================================================================
# Dockerfile.app —— 一体化调试镜像（API + H5 同源）
#
# 仅用于本地排查 / CI 冒烟：容器启动后 http://localhost:8000/ 直接打开 H5，
# 同时 /api/* 提供接口。默认 APP_ENV=dev + SQLite + mock 邮件，切勿用于生产。
#
# 这是「自包含」镜像：内部会自己构建一次 H5（适合在没有任何预构建产物的
# 场景一键构建）。只想要前端镜像请用 Dockerfile.nginx / Dockerfile。
#
# 构建上下文：仓库根（需要 frontend/ 与 backend/）。
#   docker build -f Dockerfile.app -t zaima-app .
#   docker run --rm -p 8000:8000 zaima-app
# =============================================================================

# ---------- 阶段 1：构建 H5 ----------
FROM node:22-alpine AS web
WORKDIR /web
# 先拷贝依赖清单，利用 Docker 层缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
# 拷贝前端源码并构建
COPY frontend/ ./
RUN npm run build:h5

# ---------- 阶段 2：后端运行期依赖（只装 requirements.txt） ----------
FROM python:3.13-alpine AS deps
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY backend/requirements.txt ./
RUN set -eux; \
    python -m venv /opt/venv; \
    /opt/venv/bin/pip install --no-cache-dir --no-compile -r requirements.txt; \
    # 运行期不需要安装工具，卸掉更小
    /opt/venv/bin/pip uninstall -y pip setuptools wheel >/dev/null 2>&1 || true; \
    find /opt/venv -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

# ---------- 阶段 3：运行镜像 ----------
FROM python:3.13-alpine AS runtime
ARG APP_VERSION=dev
ARG VCS_REF=unknown
# 构建号（CI 传提交短哈希）
ARG APP_BUILD=dev

LABEL org.opencontainers.image.title="zaima-app" \
      org.opencontainers.image.description="Zaima all-in-one debug image (API + H5)" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"

# 默认开发配置：SQLite + 自动建表 + mock 邮件 + 同源托管 H5。
# 注意：后端只在 APP_ENV=dev 且 STATIC_DIR 下存在 index.html 时才托管页面。
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    TZ=UTC \
    APP_ENV=dev \
    AUTO_CREATE_TABLES=true \
    RUN_MIGRATIONS=false \
    SCHEDULER_ENABLED=false \
    EMAIL_ADAPTER=mock \
    DATABASE_URL=sqlite+pysqlite:////data/zaima.db \
    STATIC_DIR=/app/static \
    APP_VERSION="${APP_VERSION}" \
    APP_BUILD="${APP_BUILD}"

# 非 root 运行，并准备可写的数据目录（SQLite / 模拟邮箱）
RUN addgroup -g 10001 -S app \
    && adduser -u 10001 -S -G app -h /app -s /sbin/nologin app \
    && mkdir -p /data && chown -R app:app /data

WORKDIR /app

# 后端依赖与代码
COPY --from=deps /opt/venv /opt/venv
COPY backend/docker-entrypoint.sh ./
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app

# 阶段 1 预构建的 H5 产物 → /app/static（与 STATIC_DIR 对应）
COPY --from=web /web/dist/build/h5 ./static

RUN chmod +x ./docker-entrypoint.sh \
    && chown -R app:app /app

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

STOPSIGNAL SIGTERM
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--timeout-graceful-shutdown", "20"]
