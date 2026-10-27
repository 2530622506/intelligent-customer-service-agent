# Intelligent Customer Service Agent

面向电商售后团队的单租户智能客服 Agent 系统。

## 当前状态

项目已完成后端核心链路和前端基础工作台，当前处于发布门禁收尾阶段。

已具备：

- FastAPI + LangGraph 受控 Agent Runtime、5 类业务 Agent、REST + SSE。
- PostgreSQL、Milvus Dense / BM25、Neo4j、RustFS、Redis、RabbitMQ 的本地 Compose 环境。
- 文档上传、MinerU Cloud 解析、版本治理、索引前发布和引用回溯。
- RBAC、DataScope、人工接管、审批、幂等、高风险动作模拟和离线评测。
- 客服工作台、知识运营台、图谱实体 / 关系审核和管理员 RBAC 配置台。

当前仍需完成正式发布前的浏览器级 SSE 断线回归、完整安全门禁报告和干净环境演示脚本。

规划文档位于上级 Trellis task：

```text
../.trellis/tasks/10-26-intelligent-customer-service-agent/
```

任务总览：

```text
../.trellis/tasks/10-26-intelligent-customer-service-agent/tasks/README.md
```

## 目录

```text
backend/       Python + FastAPI + LangGraph
frontend/      React + Vite + TypeScript + Tailwind / shadcn/ui
infra/         Docker Compose 和本地基础设施配置
fixtures/      合成脱敏文档、业务数据和评测集
docs/          API、数据模型、运行和评测说明
scripts/       初始化、健康检查和评测脚本
```

## 本地模型运行方式

本地开发默认让 Docker 只运行 PostgreSQL、Milvus、Neo4j、Redis、RabbitMQ、RustFS 和 Worker；Python API 在宿主机运行，以便直接访问 DashScope-compatible 模型服务。先启动基础设施，再运行：

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis rabbitmq milvus-etcd milvus neo4j rustfs worker
./scripts/run-host-api.sh
```

前端地址仍为 `http://127.0.0.1:55173`，Nginx 会把 `/api` 代理到宿主机 API `8001`。模型 key 从项目根目录未提交的 `.env` 读取。

## 技术基线

- FastAPI、Pydantic 2、SQLAlchemy 2 Async、asyncpg、Alembic
- LangGraph Core、LangChain
- PostgreSQL、Milvus、Neo4j、Redis、RabbitMQ、RustFS
- DashScope：`qwen3.7-flash`、`qwen3.7-text-embedding`、`qwen3.7-text-rerank`
- React、Vite、TypeScript、Tailwind、shadcn/ui、React Router
- REST + SSE

## 安全说明

真实 API Key 只允许放在本地未提交的 `.env` 中。禁止将 Langfuse、DashScope、MinerU 或其他服务密钥写入代码、文档、日志和前端构建产物。
