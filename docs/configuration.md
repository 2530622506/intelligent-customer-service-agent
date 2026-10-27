# Configuration

## Secret Handling

真实密钥只允许放在项目根目录的本地 `.env` 文件中。`.env` 已被 `.gitignore` 忽略，禁止把 Langfuse、DashScope、MinerU、数据库或对象存储密钥写入代码、文档、日志、前端构建产物或 Git 历史。

如果参考 `knowledge-hub/coding/knowledge-hub-backend/.env` 或 `.env.copy`，只复制变量的语义和连接方式，不要把旧项目无关配置带入 Git。开发机可以把该文件作为本项目未提交的本地 `.env` 来源。

## Service Mapping

| Capability | New project variables | `knowledge-hub` reference |
|---|---|---|
| Chat model | `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`CHAT_MODEL`；兼容 `DASHSCOPE_API_KEY`、`CHAT_BASE_URL` | `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`MODEL_NAME` |
| Embedding | `EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSION` | `DASHSCOPE_API_KEY`、`EMBEDDING_BASE_URL`、`EMBEDDING_MODEL` |
| Reranker | `RERANK_API_KEY`、`RERANK_BASE_URL`、`RERANK_MODEL` | `RERANK_API_KEY`、`RERANK_BASE_URL`、`RAG_RERANK_MODEL` |
| MinerU | `MINERU_API_KEY`、`MINERU_BASE_URL` | `MINERU_API_TOKEN`、`MINERU_BASE_URL`、`MINERU_API_BASE` |
| Langfuse | `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_BASE_URL` | Same variable family |
| PostgreSQL | `DATABASE_URL` | `POSTGRES_HOST`、`POSTGRES_PORT`、`POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_DB` |
| Redis | `REDIS_URL` | `REDIS_HOST`、`REDIS_PORT`、`REDIS_PASSWORD`、`REDIS_DB` |
| RabbitMQ | `RABBITMQ_URL` | `RABBITMQ_URL` |
| Neo4j | `NEO4J_URI`、`NEO4J_USER`、`NEO4J_PASSWORD` | Same variable family |
| RustFS | `RUSTFS_ENDPOINT`、`RUSTFS_ACCESS_KEY`、`RUSTFS_SECRET_KEY`、`RUSTFS_BUCKET` | S3 / MinIO / RustFS variables |

## Confirmed Model Baseline

```env
CHAT_MODEL=qwen3.7-flash
EMBEDDING_MODEL=qwen3.7-text-embedding
EMBEDDING_DIMENSION=1024
RERANK_MODEL=qwen3.7-text-rerank
EVAL_JUDGE_MODEL=qwen3.7-flash
EVAL_CONCURRENCY=2
EVAL_FILTER=
EVAL_USER_ID=eval-admin
```

`OPENAI_API_KEY` 和 `OPENAI_BASE_URL` 会自动映射到当前的 DashScope-compatible chat 配置；当没有单独填写 `EMBEDDING_API_KEY` / `RERANK_API_KEY` 时，会复用该 key。Embedding 默认使用 OpenAI-compatible `/embeddings`，与 `knowledge-hub` 的调用方式一致。

本地开发时建议使用 `scripts/run-host-api.sh` 在宿主机启动 API，Docker 只运行基础设施。这样模型请求不会经过 Docker 的外部 TLS / 代理路径；前端 Nginx 会把 `/api` 转发到宿主机 `8001`。

Embedding uses the DashScope native API with `text_type=document` for document vectors and `text_type=query` for query vectors. Reranker uses DashScope Text Rerank API and falls back to RRF when the service is unavailable.

## Local Infrastructure

`infra/docker-compose.yml` provides PostgreSQL, Redis, RabbitMQ, Milvus Standalone, Neo4j and RustFS. RustFS is used as the S3-compatible backend for both original files and Milvus object storage, so the local stack does not add a separate MinIO container. Langfuse uses Cloud in the first version. MinerU uses the Cloud API; it is not deployed as a local model service.

## Checks

Before committing configuration changes:

```bash
rg -n --hidden --glob '!.git/**' 'LANGFUSE_(PUBLIC|SECRET)_KEY=.+|DASHSCOPE_API_KEY=.+|MINERU_API_KEY=.+' .
docker compose -f infra/docker-compose.yml config
```

