#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000/api/v1}"
COOKIE_FILE="${TMPDIR:-/tmp}/csa-error-$RANDOM.cookies"
trap 'rm -f "$COOKIE_FILE"' EXIT

# 未登录的写接口必须拒绝；Cookie 认证下缺 CSRF 也必须拒绝。
status=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$API_BASE/conversations" -H 'Content-Type: application/json' -d '{}')
[ "$status" = "403" ] || [ "$status" = "401" ]

curl -fsS -c "$COOKIE_FILE" -H 'Content-Type: application/json' \
  -d '{"username":"demo-customer","password":"demo123456"}' \
  "$API_BASE/auth/login" >/dev/null

status=$(curl -sS -o /dev/null -w '%{http_code}' -b "$COOKIE_FILE" -X POST \
  "$API_BASE/workflow/conversations/00000000-0000-0000-0000-000000000000/handoff" \
  -H 'Content-Type: application/json' -d '{"reason":"no csrf"}')
[ "$status" = "403" ]

# 客户角色不得读取客服人工队列。
status=$(curl -sS -o /dev/null -w '%{http_code}' -b "$COOKIE_FILE" "$API_BASE/workflow/handoff/queue")
[ "$status" = "403" ]

# 不存在的会话不能泄露详情。
csrf=$(awk '$6=="csa_csrf_token" {print $7}' "$COOKIE_FILE")
status=$(curl -sS -o /dev/null -w '%{http_code}' -b "$COOKIE_FILE" -H "X-CSRF-Token: $csrf" \
  -X POST "$API_BASE/conversations/00000000-0000-0000-0000-000000000000/runs" \
  -H 'Content-Type: application/json' -d '{"message":"test"}')
[ "$status" = "404" ]

printf 'api error smoke passed\n'
