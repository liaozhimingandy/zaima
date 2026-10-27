#!/usr/bin/env bash
# =============================================================================
# read-config.sh -- 读取 .ci/project.config.yaml，输出扁平的 KEY=VALUE
#
# 结论：CI 以本配置文件为准（GitHub Variables 仅作缺省回退）。
# 用法：bash .ci/scripts/read-config.sh [.ci/project.config.yaml]
# 输出示例：
#   project.type=auto
#   docker.registry=docker.io
#   enable.docker_app=auto
#   static.assets_image.dockerfile=.ci/docker-assets/Dockerfile.assets
# =============================================================================
set -euo pipefail

f="${1:-.ci/project.config.yaml}"
[ -f "$f" ] || exit 0

awk '
  /^[[:space:]]*#/ { next }        # 跳过注释
  /^[[:space:]]*$/ { next }        # 跳过空行
  {
    match($0, /^ */); ind = RLENGTH
    line = $0; sub(/^ */, "", line)
    eq = index(line, ":")
    if (eq == 0) next
    k = substr(line, 1, eq - 1)
    v = substr(line, eq + 1)
    sub(/^[ \t]*/, "", v)
    sub(/[ \t]+#.*$/, "", v)        # 去掉行尾注释
    gsub(/^"|"$/, "", v)            # 去掉首尾引号
    lvl = ind / 2
    path[lvl] = k
    if (v != "") {
      full = ""
      for (i = 0; i <= lvl; i++) { if (i > 0) full = full "."; full = full path[i] }
      print full "=" v
    }
  }
' "$f"
