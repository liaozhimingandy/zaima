#!/usr/bin/env bash
# 一键触发一次「超时未确认 → 给守护人发提醒邮件」的完整流程（仅 dev 环境可用）。
#
# 用法：
#   scripts/dev-mail-test.sh                              # 默认 http://127.0.0.1:8098
#   scripts/dev-mail-test.sh http://127.0.0.1:8080        # 指定地址
#   GUARDIAN_EMAIL=me@example.com scripts/dev-mail-test.sh
#   CONTAINER=my-container scripts/dev-mail-test.sh       # 顺便导出容器内的邮件
#
# 原理：利用 dev 环境的 X-Debug-Now 请求头「伪造当前时间」，不用真的等 24 小时。

set -euo pipefail

BASE="${1:-http://127.0.0.1:8098}"
BASE="${BASE%/}"

# 固定时间轴：确认 → 次日应确认 → 再下一日超过 24h 阈值
CHECKIN_AT="${CHECKIN_AT:-2026-06-01T00:00:00Z}"   # 上海 06-01 08:00
SCAN_AT="${SCAN_AT:-2026-06-03T00:00:00Z}"         # 上海 06-03 08:00
GUARDIAN_NAME="${GUARDIAN_NAME:-妈妈}"
GUARDIAN_EMAIL="${GUARDIAN_EMAIL:-guardian@example.com}"
CONTAINER="${CONTAINER:-dev-zaima-app-01}"

RUN_ID="$(date +%s)$$"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
fail() { printf '\n\033[31m失败：%s\033[0m\n' "$*" >&2; exit 1; }

# 从紧凑 JSON 中取字段，避免依赖 jq
jget() { sed -n "s/.*\"$1\":\"\\([^\"]*\\)\".*/\\1/p" | head -1; }
jnum() { sed -n "s/.*\"$1\":\\([0-9]*\\).*/\\1/p" | head -1; }

pretty() {
  if command -v python >/dev/null 2>&1; then python -m json.tool 2>/dev/null || cat
  elif command -v python3 >/dev/null 2>&1; then python3 -m json.tool 2>/dev/null || cat
  else cat
  fi
}

say "0/5 健康检查 $BASE"
HEALTH=$(curl -sS --noproxy '*' "$BASE/api/health") || fail "无法连接 $BASE，请先启动服务"
printf '%s' "$HEALTH" | pretty
printf '%s' "$HEALTH" | grep -q '"env":"dev"' \
  || fail "当前服务不是 dev 环境：X-Debug-Now 与模拟邮件都不可用（需要 APP_ENV=dev）"

say "1/5 创建匿名账户（时区 Asia/Shanghai）"
INIT=$(curl -sS --noproxy '*' -X POST "$BASE/api/account/init" \
  -H 'Content-Type: application/json' \
  -d "{\"initKey\":\"dev-mail-$RUN_ID\",\"platform\":\"dev-script\",\"timezone\":\"Asia/Shanghai\"}")
TOKEN=$(printf '%s' "$INIT" | jget accessToken)
[ -n "$TOKEN" ] || { printf '%s\n' "$INIT"; fail "创建账户失败"; }
AUTH="Authorization: Bearer $TOKEN"
info "accountId = $(printf '%s' "$INIT" | jget accountId)"

say "2/5 添加守护人：$GUARDIAN_NAME <$GUARDIAN_EMAIL>"
ADD=$(curl -sS --noproxy '*' -X POST "$BASE/api/guardians" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"$GUARDIAN_NAME\",\"email\":\"$GUARDIAN_EMAIL\"}")
printf '%s' "$ADD" | grep -q '"code":"OK"' || { printf '%s\n' "$ADD"; fail "添加守护人失败"; }
info "ok"

say "3/5 在 $CHECKIN_AT 点「我在」"
CHECKIN=$(curl -sS --noproxy '*' -X POST "$BASE/api/checkin" -H "$AUTH" \
  -H 'Content-Type: application/json' -H "X-Debug-Now: $CHECKIN_AT" \
  -d "{\"requestId\":\"dev-checkin-$RUN_ID\"}")
printf '%s' "$CHECKIN" | grep -q '"code":"OK"' || { printf '%s\n' "$CHECKIN"; fail "确认失败"; }
info "下次应确认: $(printf '%s' "$CHECKIN" | jget nextCheckinAt)"

say "4/5 把时间推进到 $SCAN_AT 并触发扫描"
RUN=$(curl -sS --noproxy '*' -X POST "$BASE/api/dev/scheduler/run" -H "$AUTH" \
  -H "X-Debug-Now: $SCAN_AT")
printf '%s' "$RUN" | pretty
info "本次新建异常事件: $(printf '%s' "$RUN" | jnum alertsCreated)、模拟发送邮件: $(printf '%s' "$RUN" | jnum sent)"
info "（scan/dispatch 是全库统计，不只统计这个账户）"

say "5/5 查看模拟邮件"
LAST=""
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  # Git Bash 会把 /data 转成 Windows 路径，必须关闭 MSYS 路径转换
  MSYS_NO_PATHCONV=1 docker exec "$CONTAINER" sh -c 'ls -l /data/mailbox 2>/dev/null || echo "  （目录不存在，说明还没有发送过任何邮件）"'
  LAST=$(MSYS_NO_PATHCONV=1 docker exec "$CONTAINER" sh -c 'ls -1t /data/mailbox/*.eml 2>/dev/null | head -1' || true)
  if [ -n "$LAST" ]; then
    info "最新邮件：$LAST"
    OUT="${TMPDIR:-/tmp}/zaima-last.eml"
    MSYS_NO_PATHCONV=1 docker exec "$CONTAINER" cat "$LAST" > "$OUT"
    info "已导出到：$OUT"
    python - "$OUT" <<'PY' || sed -n '1,12p' "$OUT"
import sys, email, email.policy
msg = email.message_from_file(
    open(sys.argv[1], encoding="utf-8", errors="replace"), policy=email.policy.default
)
print("  Subject:", msg["subject"])
print("  To     :", msg["to"])
body = msg.get_body(preferencelist=("plain",))
if body:
    print("  ---- 正文 ----")
    for line in body.get_content().splitlines()[:18]:
        print("  " + line)
PY
  else
    info "/data/mailbox 里没有 .eml 文件，继续看接口侧的任务状态："
    curl -sS --noproxy '*' "$BASE/api/dev/notifications" -H "$AUTH" | pretty
  fi
else
  info "未检测到运行中的容器「$CONTAINER」，改看接口侧任务状态："
  curl -sS --noproxy '*' "$BASE/api/dev/notifications" -H "$AUTH" | pretty
  info "宿主机查看邮件（Git Bash 需加 MSYS_NO_PATHCONV=1）："
  info "  MSYS_NO_PATHCONV=1 docker exec $CONTAINER ls -l /data/mailbox"
fi

say "完成"
info "账户凭证（可继续手工调试）："
info "  export TOKEN=$TOKEN"
info "  curl -s $BASE/api/checkin/status -H \"Authorization: Bearer \$TOKEN\" -H 'X-Debug-Now: 2026-06-03T01:00:00Z'"
