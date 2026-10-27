#!/usr/bin/env bash
# =============================================================================
# detect-frontend.sh -- 自动定位前端工程目录、锁文件与包管理器
#
# 解决的问题：
#   1) 前端不一定在仓库根（可能在 frontend/ web/ client/ 等子目录）
#   2) actions/setup-node 的 cache 必须与包管理器匹配，否则报
#      “Dependencies lock file is not found”
#
# 输出（KEY=VALUE，可直接 >> $GITHUB_OUTPUT）：
#   frontend_dir   前端目录（相对仓库根；无则 "."）
#   frontend_lock  锁文件路径（无则空）
#   frontend_pm    包管理器：npm / yarn / pnpm（默认 npm）
#   has_frontend   true/false
# =============================================================================
set -euo pipefail

root="${1:-.}"
cd "$root"

list_pkgs() {
  find . -maxdepth 4 -name package.json \
    -not -path '*/node_modules/*' \
    -not -path './.git/*' \
    -not -path './.ci/*' 2>/dev/null | sort
}

best=""; best_lock=""; best_pm="npm"
while IFS= read -r pkg; do
  [ -n "$pkg" ] || continue
  d=$(dirname "$pkg"); d="${d#./}"; [ -z "$d" ] && d="."
  lock=""; pm="npm"
  for l in package-lock.json npm-shrinkwrap.json yarn.lock pnpm-lock.yaml; do
    if [ -f "$d/$l" ]; then
      lock="$d/$l"
      case "$l" in
        pnpm-lock.yaml) pm=pnpm ;;
        yarn.lock)      pm=yarn ;;
        *)              pm=npm  ;;
      esac
      break
    fi
  done
  if [ -n "$lock" ]; then
    # 有锁文件优先；多个时取路径最短（最浅）
    if [ -z "$best_lock" ] || [ "${#d}" -lt "${#best}" ]; then best="$d"; best_lock="$lock"; best_pm="$pm"; fi
  elif [ -z "$best" ]; then
    best="$d"
  fi
done < <(list_pkgs)

echo "frontend_dir=${best:-.}"
echo "frontend_lock=${best_lock}"
echo "frontend_pm=${best_pm:-npm}"
echo "has_frontend=$([ -n "$best" ] && echo true || echo false)"

echo "detected frontend: dir=${best:-.} lock=${best_lock:-<none>} pm=${best_pm:-npm}" >&2
