#!/usr/bin/env bash
# 镜像构建推送后执行
# 可用环境变量: IMAGE_TAGS（换行分隔的标签列表）
set -euo pipefail

echo "== post-build hook =="
echo "已推送镜像标签:"
echo "${IMAGE_TAGS:-}"
# 例如：镜像漏洞扫描、推送 SBOM、通知
#   trivy image --exit-code 0 "${IMAGE_TAGS%%$'\n'*}"
exit 0
