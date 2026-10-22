# 不使用 # syntax=docker/dockerfile:1 前端镜像：本文件只用到经典构建特性，
# 去掉后可减少一次对 Docker Hub 的依赖，离线/受限网络下也能构建。
ARG PYTHON_IMAGE=python:3.13-slim

# ---------- 构建阶段：只装依赖，不携带工具链到运行镜像 ----------
FROM ${PYTHON_IMAGE} AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---------- 运行阶段 ----------
FROM ${PYTHON_IMAGE} AS runtime

ARG APP_VERSION=dev
ARG VCS_REF=unknown

LABEL org.opencontainers.image.title="zaima-api" \
      org.opencontainers.image.description="Zaima API - daily safety check-in service" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.licenses="MIT"

# 安全默认：镜像内不预置任何环境专属配置，
# 生产必须由部署阶段注入 DATABASE_URL / SMTP_* 等变量。
# APP_ENV=prod 保证即使忘记设置也不会暴露 /api/dev/* 调试接口。
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    TZ=UTC \
    APP_ENV=prod \
    AUTO_CREATE_TABLES=false \
    RUN_MIGRATIONS=false

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY docker-entrypoint.sh ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN chmod +x ./docker-entrypoint.sh \
    && mkdir -p /app/.mailbox \
    && chown -R app:app /app

USER app

EXPOSE 8000

# 使用应用自身的健康检查接口，容器编排可据此判断就绪
HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=5 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

# 使用 exec 形式的入口脚本，SIGTERM 会传递给 uvicorn，实现优雅退出
STOPSIGNAL SIGTERM

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--timeout-graceful-shutdown", "20"]
