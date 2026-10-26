#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
DB_URL="${DATABASE_URL:-postgresql+asyncpg://app:app@127.0.0.1:15432/customer_service}"
DATABASE_URL="$DB_URL" \
  .venv-new/bin/python scripts/seed_eval_fixtures.py > /tmp/csa-eval-dataset-id.txt
DATASET_ID=$(tail -n 1 /tmp/csa-eval-dataset-id.txt)
DATABASE_URL="$DB_URL" .venv-new/bin/python scripts/run_eval.py "$DATASET_ID"
