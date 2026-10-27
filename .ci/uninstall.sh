#!/usr/bin/env bash
# =============================================================================
# uninstall.sh -- 卸载由 install.sh 安装的文件
#
# 依据 .ci/.install-manifest 精确删除「我们装的」文件，不碰你的项目代码。
# 用法：
#   bash uninstall.sh /path/to/project
#   bash uninstall.sh /path/to/project --dry-run
#   bash uninstall.sh /path/to/project --purge-config   # 连 project.config.yaml 一起删
# =============================================================================
set -euo pipefail

TARGET="."; DRY_RUN=false; PURGE=false
for a in "$@"; do
  case "$a" in
    --dry-run)      DRY_RUN=true ;;
    --purge-config) PURGE=true ;;
    -*) echo "未知参数: $a" >&2; exit 1 ;;
    *)  TARGET="$a" ;;
  esac
done

TARGET="$(cd "$TARGET" && pwd)"
M="$TARGET/.ci/.install-manifest"

if [ ! -f "$M" ]; then
  echo "未找到安装清单：$M" >&2
  echo "无法安全卸载（可能是旧版安装或并非由本模板安装）。" >&2
  exit 1
fi

echo "从 $TARGET 卸载（依据 .ci/.install-manifest）"
$DRY_RUN && echo "*** DRY-RUN：不会删除任何文件 ***"
echo "------------------------------------------------------------"

removed=0; kept=0
while IFS= read -r rel; do
  case "$rel" in ''|'#'*) continue ;; esac
  if [ "$rel" = ".ci/project.config.yaml" ] && ! $PURGE; then
    echo "KEEP   $rel  (默认保留，用 --purge-config 一并删除)"
    kept=$((kept+1)); continue
  fi
  if [ -e "$TARGET/$rel" ]; then
    if $DRY_RUN; then echo "REMOVE $rel"; else rm -f "$TARGET/$rel"; echo "REMOVE $rel"; fi
    removed=$((removed+1))
  fi
done < "$M"

if [ "$DRY_RUN" = false ]; then
  # 若配置未被保留，清单也一并删除
  if [ ! -e "$TARGET/.ci/project.config.yaml" ]; then rm -f "$M" 2>/dev/null || true; fi
  # 自底向上删除空目录（.github/workflows、.github、.ci 等；非空则保留）
  find "$TARGET/.ci" -type d -empty -delete 2>/dev/null || true
  rmdir "$TARGET/.github/workflows" 2>/dev/null || true
  rmdir "$TARGET/.github" 2>/dev/null || true
fi

echo "------------------------------------------------------------"
echo "完成：删除 $removed 项，保留 $kept 项。"
if [ "$kept" -gt 0 ]; then
  echo "提示：配置仍在 .ci/project.config.yaml；如需彻底删除，请加 --purge-config。"
fi
