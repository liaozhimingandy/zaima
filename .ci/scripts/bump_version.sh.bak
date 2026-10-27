#!/usr/bin/env bash
# bump_version.sh -- 语义化版本自增（公共工具）
# 用法:
#   scripts/bump_version.sh patch   # 1.2.3 -> 1.2.4
#   scripts/bump_version.sh minor   # 1.2.3 -> 1.3.0
#   scripts/bump_version.sh major   # 1.2.3 -> 2.0.0
# 版本来源优先级: VERSION > pyproject.toml > project.config.yaml
#   （CI 中优先用 git tag；无 tag 时回退读 VERSION，故本地建议维护 VERSION 文件）
set -euo pipefail

PART="${1:-patch}"

# 跨平台 sed -i（macOS 需要空备份后缀）
sedi() { if sed --version >/dev/null 2>&1; then sed -i -E "$@"; else sed -i '' -E "$@"; fi; }

FILE=""; CUR=""
if [ -f VERSION ]; then
  CUR=$(tr -d '[:space:]' < VERSION); FILE=VERSION
elif [ -f pyproject.toml ]; then
  CUR=$(grep -m1 '^version' pyproject.toml | sed -E 's/.*"([0-9]+\.[0-9]+\.[0-9]+)".*/\1/'); FILE=pyproject.toml
elif [ -f project.config.yaml ]; then
  CUR=$(grep -m1 'version:' project.config.yaml | sed -E 's/.*([0-9]+\.[0-9]+\.[0-9]+).*/\1/'); FILE=project.config.yaml
fi

if [ -z "${CUR:-}" ]; then
  echo "未找到版本号（VERSION / pyproject.toml / project.config.yaml）" >&2
  exit 1
fi

IFS='.' read -r MAJ MIN PAT <<< "$CUR"
case "$PART" in
  major) MAJ=$((MAJ+1)); MIN=0; PAT=0 ;;
  minor) MIN=$((MIN+1)); PAT=0 ;;
  patch|*) PAT=$((PAT+1)) ;;
esac
NEW="$MAJ.$MIN.$PAT"

case "$FILE" in
  VERSION)             echo -n "$NEW" > VERSION ;;
  pyproject.toml)      sedi "s/^(version = ).*/\1\"$NEW\"/" pyproject.toml ;;
  project.config.yaml) sedi "s/^(  version: ).*/\1$NEW/" project.config.yaml ;;
esac

cat <<EOF
version: $CUR -> $NEW ($FILE)

下一步（构建号由 CI 自动生成，无需手动维护）：
  git add . && git commit -m "chore(release): v$NEW"
  git tag v$NEW && git push --tags

镜像标签预期：
  :$NEW-b<BUILD_NUMBER>   # 本次打包，精确可定位（BUILD_NUMBER=github.run_number，自增）
  :$NEW                   # 语义版本（仅 v$NEW tag）
  :sha-<commit>           # 回滚锚点
EOF
