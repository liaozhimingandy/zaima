#!/usr/bin/env bash
# =============================================================================
# ci.sh -- 项目统一 CI 入口（公共模板）
#
# 用法：bash .ci/ci.sh <install|lint|typecheck|test|build|package|all>
#
# 解析优先级（每个阶段独立判断）：
#   1) .ci/project.config.yaml 的 ci.<stage> 命令
#   2) .ci/stages/<stage>.sh 自定义脚本
#   3) Makefile 中同名目标（ci.entry=auto/make 时）
#   4) 内置探测（npm/pytest/ruff/tsc…）
#
# 这样 GitHub Actions 只需调用本项目入口，不同技术栈各自实现，互不影响。
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
STAGE="${1:-all}"
export PATH="$HOME/.local/bin:$PATH"

# ---- 读取项目配置 ----
CFG=""
if [ -f .ci/project.config.yaml ] && [ -f .ci/scripts/read-config.sh ]; then
  CFG="$(bash .ci/scripts/read-config.sh .ci/project.config.yaml 2>/dev/null || true)"
fi
get() { printf '%s\n' "$CFG" | grep -E "^$1=" | head -1 | cut -d= -f2- || true; }

# ---- 探测前后端（优先使用外部传入的环境变量，避免重复探测） ----
if [ -z "${FE_DIR:-}" ] || [ -z "${BE_DIR:-}" ]; then
  DET=""
  if [ -f .ci/scripts/detect-frontend.sh ]; then
    DET="$(bash .ci/scripts/detect-frontend.sh 2>/dev/null || true)"
  fi
  dget() { printf '%s\n' "$DET" | grep -E "^$1=" | head -1 | cut -d= -f2- || true; }
  : "${FE_DIR:=$(dget frontend_dir)}"; FE_DIR="${FE_DIR:-.}"
  : "${FE_PM:=$(dget frontend_pm)}";   FE_PM="${FE_PM:-npm}"
  : "${FE_LOCK:=$(dget frontend_lock)}"
  : "${FE_BUILD_CMD:=$(dget frontend_build_cmd)}"
  : "${BE_DIR:=$(dget backend_dir)}";  BE_DIR="${BE_DIR:-.}"
  : "${HAS_FE:=$(dget has_frontend)}"; HAS_FE="${HAS_FE:-false}"
  : "${HAS_BE:=$(dget has_backend)}";  HAS_BE="${HAS_BE:-false}"
fi

ENTRY="$(get ci.entry)"; [ -z "$ENTRY" ] && ENTRY=auto
echo "ci: stage=$STAGE entry=$ENTRY frontend=$HAS_FE($FE_DIR) backend=$HAS_BE($BE_DIR)"

# ---- 内置实现（仅在未声明命令时使用） ----
ensure_uv() {
  command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
}

install_fe() {
  [ "$HAS_FE" = "true" ] || return 0
  ( cd "$FE_DIR"
    if [ -z "$FE_LOCK" ]; then npm install
    elif [ "$FE_PM" = "pnpm" ]; then corepack enable; pnpm install --frozen-lockfile
    elif [ "$FE_PM" = "yarn" ]; then yarn install --frozen-lockfile
    else npm ci; fi )
}
install_be() {
  [ "$HAS_BE" = "true" ] || return 0
  ( cd "$BE_DIR"
    ensure_uv
    if [ -f pyproject.toml ]; then uv sync --no-dev || uv sync
    elif [ -f requirements.txt ]; then pip install -r requirements.txt; fi )
}

builtin() {
  local s="$1"
  case "$s" in
    install)
      install_be; install_fe ;;
    lint)
      if [ "$HAS_BE" = "true" ] && { [ -f "$BE_DIR/.ruff.toml" ] || grep -q '\[tool\.ruff' "$BE_DIR/pyproject.toml" 2>/dev/null; }; then
        ( cd "$BE_DIR"; ensure_uv; uv run --with ruff ruff check . )
      fi
      if [ "$HAS_FE" = "true" ] && grep -q '"lint"[[:space:]]*:' "$FE_DIR/package.json" 2>/dev/null; then
        ( cd "$FE_DIR"; npm run lint )
      fi ;;
    typecheck)
      if [ "$HAS_FE" = "true" ] && { grep -q '"typecheck"[[:space:]]*:' "$FE_DIR/package.json" 2>/dev/null || [ -f "$FE_DIR/tsconfig.json" ]; }; then
        ( cd "$FE_DIR"; npm run typecheck --if-present || npx tsc --noEmit )
      fi
      if [ "$HAS_BE" = "true" ] && { [ -f "$BE_DIR/mypy.ini" ] || grep -q '\[tool\.mypy' "$BE_DIR/pyproject.toml" 2>/dev/null; }; then
        ( cd "$BE_DIR"; ensure_uv; uv run --with mypy mypy . )
      fi ;;
    test)
      if [ "$HAS_BE" = "true" ] && { [ -d "$BE_DIR/tests" ] || [ -f "$BE_DIR/pytest.ini" ] || grep -q '\[tool\.pytest' "$BE_DIR/pyproject.toml" 2>/dev/null; }; then
        ( cd "$BE_DIR"; ensure_uv; uv run --with pytest pytest -q )
      fi
      if [ "$HAS_FE" = "true" ] && grep -q '"test"[[:space:]]*:' "$FE_DIR/package.json" 2>/dev/null; then
        ( cd "$FE_DIR"; npm test )
      fi ;;
    build)
      if [ "$HAS_FE" = "true" ]; then
        local cmd; cmd="$(get static.build_command)"
        # 配置为默认 npm run build 时，优先使用探测到的 build/build:* 脚本
        if [ "$cmd" = "npm run build" ] && [ -n "$FE_BUILD_CMD" ] && [ "$FE_BUILD_CMD" != "npm run build" ]; then
          cmd="$FE_BUILD_CMD"
        fi
        [ -z "$cmd" ] && cmd="npm run build"
        if [ "$cmd" = "npm run build" ] && ! grep -q '"build"[[:space:]]*:' "$FE_DIR/package.json" 2>/dev/null; then
          echo "::error::前端目录($FE_DIR)没有 build 脚本，请设置 static.build_command 或 ci.build"
          exit 1
        fi
        ( cd "$FE_DIR"; echo "frontend build: $cmd"; bash -c "$cmd" )
      fi
      if [ "$HAS_BE" = "true" ] && [ -f "$BE_DIR/pyproject.toml" ]; then
        ( cd "$BE_DIR"; ensure_uv; uv build || python -m build )
      fi ;;
    package)
      # 默认不打包；项目用 ci.package 或 .ci/stages/package.sh 自定义
      echo "package: 未声明打包步骤（可用 ci.package 或 .ci/stages/package.sh）" ;;
    *)
      echo "未知阶段: $s" >&2; return 1 ;;
  esac
}

run_stage() {
  local s="$1"
  local c; c="$(get "ci.$s")"
  if [ -n "$c" ]; then
    echo ">>> [$s] $c"
    bash -c "$c"
    return
  fi
  if [ -f ".ci/stages/$s.sh" ]; then
    echo ">>> [$s] bash .ci/stages/$s.sh"
    bash ".ci/stages/$s.sh"
    return
  fi
  if { [ "$ENTRY" = "make" ] || [ "$ENTRY" = "auto" ]; } && [ -f Makefile ] && grep -Eq "^$s:" Makefile; then
    echo ">>> [$s] make $s"
    make "$s"
    return
  fi
  builtin "$s"
}

case "$STAGE" in
  all|ci)
    run_stage install
    run_stage lint
    run_stage typecheck
    run_stage test
    run_stage build
    ;;
  *)
    run_stage "$STAGE"
    ;;
esac
