#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS}" = "true" ]; then
  echo "[entrypoint] 执行数据库迁移 alembic upgrade head"
  alembic upgrade head
fi

exec "$@"
