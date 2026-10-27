#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# 宿主机直连 DashScope，避免 Docker 容器的 TLS / 代理路径影响模型调用。
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy

export PYTHONPATH="$ROOT_DIR/backend"
export APP_ENV="development"
export DATABASE_URL="postgresql+asyncpg://app:app@localhost:15432/customer_service"
export REDIS_URL="redis://localhost:16379/0"
export RABBITMQ_URL="amqp://guest:guest@localhost:25672/"
export MILVUS_URI="http://localhost:19530"
export NEO4J_URI="bolt://localhost:17687"
export RUSTFS_ENDPOINT="http://localhost:19000"
export CHAT_MODEL="qwen3.7-flash"
export EMBEDDING_MODEL="qwen3.7-text-embedding"
export EMBEDDING_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export RERANK_MODEL="qwen3.7-text-rerank"
export RERANK_BASE_URL="https://dashscope.aliyuncs.com"
export MODEL_HTTP_TRUST_ENV="false"

exec "$ROOT_DIR/backend/.venv-new/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8001
