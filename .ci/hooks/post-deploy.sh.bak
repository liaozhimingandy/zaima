#!/usr/bin/env bash
# 部署后执行（Cloudflare Pages 部署后）
# 可用环境变量: DEPLOY_URL / CLOUDFLARE_PROJECT
set -euo pipefail

echo "== post-deploy hook =="
echo "部署地址: ${DEPLOY_URL:-}"
# 例如：刷新 CDN 缓存、健康检查、通知
#   curl -X POST "${DEPLOY_URL}/health"
exit 0
