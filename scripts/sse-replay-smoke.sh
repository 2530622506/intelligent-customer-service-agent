#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000/api/v1}"
COOKIE_FILE="${TMPDIR:-/tmp}/csa-sse-replay-$RANDOM.cookies"
FIRST_STREAM="${TMPDIR:-/tmp}/csa-sse-replay-$RANDOM.first"
SECOND_STREAM="${TMPDIR:-/tmp}/csa-sse-replay-$RANDOM.second"
IDEMPOTENCY_KEY="sse-replay-smoke-$RANDOM"
trap 'rm -f "$COOKIE_FILE" "$FIRST_STREAM" "$SECOND_STREAM"' EXIT

# 先用稳定的幂等键创建 Run，再模拟客户端很短的 SSE 连接窗口。
curl -fsS -c "$COOKIE_FILE" \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo-admin","password":"demo123456"}' \
  "$API_BASE/auth/login" >/dev/null

CSRF=$(awk '$6=="csa_csrf_token" {print $7}' "$COOKIE_FILE")
CONVERSATION=$(curl -fsS -b "$COOKIE_FILE" \
  -H "X-CSRF-Token: $CSRF" \
  -H 'Content-Type: application/json' \
  -d '{"title":"sse replay smoke"}' \
  "$API_BASE/conversations")
CONVERSATION_ID=$(printf '%s' "$CONVERSATION" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

RUN=$(curl -fsS -b "$COOKIE_FILE" \
  -H "X-CSRF-Token: $CSRF" \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -d '{"message":"退货政策是什么？"}' \
  "$API_BASE/conversations/$CONVERSATION_ID/runs")
RUN_ID=$(printf '%s' "$RUN" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

# 断线只影响网络输出，服务端仍会持久化结果；curl 超时属于预期行为。
curl -sS -N --max-time 0.01 -X POST -b "$COOKIE_FILE" \
  -H 'Accept: text/event-stream' \
  -H "X-CSRF-Token: $CSRF" \
  "$API_BASE/conversations/$CONVERSATION_ID/runs/$RUN_ID/stream" >"$FIRST_STREAM" || true

sleep 0.2

# 第二次连接必须命中 completed replay 分支，不重新执行 Agent。
replayed=false
for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -sS -N --max-time 2 -X POST -b "$COOKIE_FILE" \
    -H 'Accept: text/event-stream' \
    -H "X-CSRF-Token: $CSRF" \
    "$API_BASE/conversations/$CONVERSATION_ID/runs/$RUN_ID/stream" >"$SECOND_STREAM" || true
  if rg -q '"replay":true' "$SECOND_STREAM"; then
    replayed=true
    break
  fi
  sleep 0.2
done
[ "$replayed" = true ]

RETRY=$(curl -fsS -b "$COOKIE_FILE" \
  -H "X-CSRF-Token: $CSRF" \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -d '{"message":"退货政策是什么？"}' \
  "$API_BASE/conversations/$CONVERSATION_ID/runs")
RETRY_ID=$(printf '%s' "$RETRY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
[ "$RUN_ID" = "$RETRY_ID" ]

printf 'sse replay smoke passed: run=%s\n' "$RUN_ID"
