#!/usr/bin/env bash
# 镜像构建前执行（docker-app / docker-assets 均会调用）
# 可用环境变量: PROJECT_TYPE / DOCKER_IMAGE
set -euo pipefail

echo "== pre-build hook =="
# 例如：生成版本文件、拉取私有依赖、注入构建参数
#   echo "${GITHUB_SHA}" > src/version.txt
#   uv export -o requirements.lock   # 若基础镜像需离线依赖
exit 0
