#!/usr/bin/env bash
# 由 install.sh 生成：把本项目的配置写入 GitHub Variables
# 用法: bash scripts/apply-github-config.sh [owner/repo]
set -euo pipefail
REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
command -v gh >/dev/null || { echo "未安装 gh CLI，请到 GitHub 网页手动设置 Variables"; exit 1; }
set_var() { gh variable set "$1" --body "$2" --repo "$REPO"; echo "  $1=$2"; }
echo "写入 Variables 到 $REPO ..."
set_var REGISTRY "docker.io"
set_var DOCKER_IMAGE "liaozhiming/zaima"
set_var DOCKERFILE_PATH "Dockerfile"
set_var ENABLE_DOCKER_APP "auto"
set_var ENABLE_DOCKER_ASSETS "auto"
set_var ENABLE_STATIC_CLOUDFLARE "true"
set_var STATIC_BUILD_CMD "npm run build:h5"
set_var STATIC_DIST_DIR "dist"
set_var ASSETS_DOCKERFILE ".ci/docker-assets/Dockerfile.assets"
if [ -n "zaima" ]; then set_var CLOUDFLARE_PROJECT "zaima"; fi
echo
echo "Secrets 需手动设置（值不落盘）:"
echo "  gh secret set DOCKER_USERNAME       --repo $REPO"
echo "  gh secret set DOCKER_PASSWORD       --repo $REPO"
if [ "true" = "true" ]; then
  echo "  gh secret set CLOUDFLARE_API_TOKEN  --repo $REPO"
  echo "  gh secret set CLOUDFLARE_ACCOUNT_ID --repo $REPO"
fi
