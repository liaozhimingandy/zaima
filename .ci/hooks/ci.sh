#!/usr/bin/env bash
# 用户自定义 CI 步骤（在 lint/test 之后运行）
# 可用环境变量: PROJECT_TYPE / IS_BACKEND / IS_FRONTEND
set -euo pipefail

echo "== custom ci hook =="
# 在此添加项目专属检查，例如：
#   uv run mypy src/          # Python 类型检查
#   npm run typecheck         # 前端类型检查
#   bash scripts/contract_test.sh
exit 0
