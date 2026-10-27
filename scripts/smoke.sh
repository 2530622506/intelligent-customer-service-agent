#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000/api/v1}"
COOKIE_FILE="${TMPDIR:-/tmp}/csa-smoke-$RANDOM.cookies"

cleanup() {
  rm -f "$COOKIE_FILE"
}
trap cleanup EXIT

# 先验证基础设施 readiness，再开始业务 API smoke。
curl -fsS "$API_BASE/health/ready" >/dev/null

curl -fsS -c "$COOKIE_FILE" \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo-admin","password":"demo123456"}' \
  "$API_BASE/auth/login" >/dev/null

CSRF=$(awk '$6=="csa_csrf_token" {print $7}' "$COOKIE_FILE")

CONVERSATION=$(curl -fsS -b "$COOKIE_FILE" \
  -H "X-CSRF-Token: $CSRF" \
  -H 'Content-Type: application/json' \
  -d '{"title":"smoke conversation"}' \
  "$API_BASE/conversations")
CONVERSATION_ID=$(printf '%s' "$CONVERSATION" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

RUN=$(curl -fsS -b "$COOKIE_FILE" \
  -H "X-CSRF-Token: $CSRF" \
  -H 'Content-Type: application/json' \
  -d '{"message":"退货政策是什么？"}' \
  "$API_BASE/conversations/$CONVERSATION_ID/runs")
RUN_ID=$(printf '%s' "$RUN" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

# SSE smoke 只检查关键事件，完整断线恢复由接口集成测试覆盖。
STREAM=$(curl -fsS -N -X POST -b "$COOKIE_FILE" \
  -H 'Accept: text/event-stream' \
  -H "X-CSRF-Token: $CSRF" \
  "$API_BASE/conversations/$CONVERSATION_ID/runs/$RUN_ID/stream")
printf '%s' "$STREAM" | rg -q 'event: run_started'
printf '%s' "$STREAM" | rg -q 'event: done'

curl -fsS -b "$COOKIE_FILE" "$API_BASE/knowledge/entities" >/dev/null
curl -fsS -b "$COOKIE_FILE" "$API_BASE/evaluations/datasets" >/dev/null

printf 'smoke passed: conversation=%s run=%s\n' "$CONVERSATION_ID" "$RUN_ID"
