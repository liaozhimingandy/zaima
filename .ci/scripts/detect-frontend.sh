#!/usr/bin/env bash
# =============================================================================
# detect-frontend.sh -- 自动定位前端/后端工程目录（含锁文件、包管理器、构建脚本）
#
# 解决问题：
#   1) 前后端不一定在仓库根（可能在 frontend/ web/ client/ backend/ server/ 等子目录）
#   2) setup-node 的 cache 必须与包管理器匹配，否则报 “Dependencies lock file is not found”
#   3) 仓库根可能有一个“工具型” package.json（无 build），真正前端在子目录
#
# 前端选择规则（打分）：有 build 脚本 +2，有锁文件 +1，路径越浅越优先。
# 后端选择规则：pyproject.toml / requirements.txt / setup.py，路径越浅越优先。
#
# 输出（KEY=VALUE，可直接 >> $GITHUB_OUTPUT）：
#   frontend_dir / frontend_lock / frontend_pm / has_frontend
#   frontend_has_build / frontend_build_script / frontend_build_cmd
#   backend_dir / has_backend
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

best=""; best_lock=""; best_pm="npm"; best_script=""; best_rank=-999
while IFS= read -r pkg; do
  [ -n "$pkg" ] || continue
  d=$(dirname "$pkg"); d="${d#./}"; [ -z "$d" ] && d="."

  # 锁文件与包管理器
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

  # 构建脚本：优先精确 build；否则任取一个 build:*（如 build:h5 / build:prod / build:web）
  script=""
  if grep -Eq '"build"[[:space:]]*:' "$pkg"; then
    script="build"
  else
    script="$(grep -oE '"build:[a-zA-Z0-9._-]+"[[:space:]]*:' "$pkg" 2>/dev/null | head -1 | sed -E 's/^"([^"]+)".*/\1/' || true)"
  fi

  # 打分：build 脚本 +2，锁文件 +1；深度越浅越优先
  score=0; [ -n "$script" ] && score=$((score+2)); [ -n "$lock" ] && score=$((score+1))
  depth=$(awk -F/ '{print NF-1}' <<< "$pkg")
  rank=$((score*10 - depth))

  if [ "$rank" -gt "$best_rank" ]; then
    best="$d"; best_lock="$lock"; best_pm="$pm"; best_script="$script"; best_rank="$rank"
  fi
done < <(list_pkgs)

# 后端目录：找 pyproject.toml / requirements.txt / setup.py（排除 node_modules/.git/.ci），取最浅
backend=""; backend_rank=-999
while IFS= read -r f; do
  [ -n "$f" ] || continue
  d=$(dirname "$f"); d="${d#./}"; [ -z "$d" ] && d="."
  depth=$(awk -F/ '{print NF-1}' <<< "$f")
  rank=$((0 - depth))
  if [ "$rank" -gt "$backend_rank" ]; then backend="$d"; backend_rank="$rank"; fi
done < <(find . -maxdepth 4 \( -name pyproject.toml -o -name requirements.txt -o -name setup.py \) \
           -not -path '*/node_modules/*' -not -path './.git/*' -not -path './.ci/*' 2>/dev/null | sort)

echo "frontend_dir=${best:-.}"
echo "frontend_lock=${best_lock}"
echo "frontend_pm=${best_pm:-npm}"
echo "has_frontend=$([ -n "$best" ] && echo true || echo false)"
echo "frontend_has_build=$([ -n "$best_script" ] && echo true || echo false)"
echo "frontend_build_script=${best_script}"
echo "frontend_build_cmd=$([ -n "$best_script" ] && echo "npm run $best_script" || echo "")"
echo "backend_dir=${backend:-.}"
echo "has_backend=$([ -n "$backend" ] && echo true || echo false)"

echo "detected frontend: dir=${best:-.} lock=${best_lock:-<none>} pm=${best_pm:-npm} build=${best_script:-<none>}" >&2
echo "detected backend:  dir=${backend:-.}" >&2
