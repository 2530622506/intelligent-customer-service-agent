# Intelligent Customer Service Agent

面向电商售后团队的单租户智能客服 Agent 系统。

## 当前状态

项目处于规划和工程初始化阶段，暂未开始业务代码实现。

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

## 技术基线

- FastAPI、Pydantic 2、SQLAlchemy 2 Async、asyncpg、Alembic
- LangGraph Core、LangChain
- PostgreSQL、Milvus、Neo4j、Redis、RabbitMQ、RustFS
- DashScope：`qwen3.7-flash`、`qwen3.7-text-embedding`、`qwen3.7-text-rerank`
- React、Vite、TypeScript、Tailwind、shadcn/ui、React Router
- REST + SSE

## 安全说明

真实 API Key 只允许放在本地未提交的 `.env` 中。禁止将 Langfuse、DashScope、MinerU 或其他服务密钥写入代码、文档、日志和前端构建产物。
