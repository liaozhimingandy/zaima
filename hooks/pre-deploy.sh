#!/usr/bin/env bash
# 部署前执行（Cloudflare Pages 部署前）
# 可用环境变量: CLOUDFLARE_PROJECT / STATIC_DIST_DIR
set -euo pipefail

echo "== pre-deploy hook =="
# 例如：部署前备份、预检
exit 0
