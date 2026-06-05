# learning_rag

当前仓库的主线目标，已经不是单纯的本地 CLI RAG Demo，而是：

- 把 `D:\code\learning_rag` 改造成可供 `E:\code\geminiBlog` 调用的 FastAPI RAG 后端

当前后端已经具备这些核心能力：

- 从 `geminiBlog` 的 PostgreSQL `Post` 表读取文章真源
- 解析 Markdown 正文、标题路径和图片引用
- 生成文本向量、图片 OCR / caption 文本特征
- 基于 `LangGraph` 执行图文问答
- 支持按 `session_id` 隔离的多轮会话和摘要记忆
- 提供普通问答、流式问答、会话查询和同步接口
- 提供博客前端接入文档、维护文档和排错文档

## 当前主线文档

### API 与接入

- `docs/api/overview.md`
- `docs/api/chat.md`
- `docs/api/ingest.md`
- `docs/integration/geminiblog-chatbot.md`

### 后端维护

- `docs/backend/architecture.md`
- `docs/backend/configuration.md`
- `docs/backend/context-budget.md`
- `docs/backend/data-flow.md`

### 排错

- `docs/troubleshooting/database.md`
- `docs/troubleshooting/api-debugging.md`
- `docs/troubleshooting/ocr-and-images.md`

### 规格与计划

- `specs/001-fastapi-rag-backend/spec.md`
- `specs/001-fastapi-rag-backend/plan.md`
- `specs/001-fastapi-rag-backend/research.md`
- `specs/001-fastapi-rag-backend/data-model.md`
- `specs/001-fastapi-rag-backend/quickstart.md`
- `specs/001-fastapi-rag-backend/tasks.md`

## 快速启动

### 1. 安装依赖

```powershell
uv sync
```

### 2. 配置 `.env`

最少建议配置：

```env
DATABASE_URL=postgresql+psycopg://blog:blog_password@127.0.0.1:5432/blog
RAG_SCHEMA=rag

OPENAI_API_KEY=你的百炼Key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
RERANK_BASE_URL=https://dashscope.aliyuncs.com/compatible-api/v1
BLOG_PUBLIC_BASE_URL=https://你的博客域名
```

如果数据库密码里包含 `@`、`:`、`/` 这类特殊字符，记得先做 URL 编码。

例如：

- 原密码：`password@123`
- 连接串中写成：`password%40123`

更多配置项请看：

- `docs/backend/configuration.md`

上下文预算默认值与调优建议请看：

- `docs/backend/context-budget.md`

### 3. 初始化数据库

```powershell
uv run alembic upgrade head
```

如果目标库还没启用 `pgvector`，先执行：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

如果你使用的是 `E:\code\geminiBlog\docker-compose.yml` 的最新版本，空库首次初始化时会自动启用 `pgvector`。

如果是旧的数据库 volume 或更早创建的云上实例，仍然要手动补一次上面的 `CREATE EXTENSION`。

当前百炼 `text-embedding-v4` 的单次批量输入上限按 `10` 处理，所以默认 `EMBEDDING_BATCH_SIZE` 也已经收敛到 `10`。

### 4. 启动服务

```powershell
uv run uvicorn app.main:app --reload
```

默认地址：

- `http://127.0.0.1:8000`

健康检查：

```powershell
Invoke-RestMethod -Method GET -Uri http://127.0.0.1:8000/health
```

## 常用命令

### 同步单篇文章

```powershell
uv run python scripts/sync_single_post.py --slug hello-nextjs
```

### 全量重建

```powershell
uv run python scripts/sync_all_posts.py --scope all
```

### 运行测试

```powershell
uv run pytest
```

### 查看迁移 SQL

```powershell
uv run alembic upgrade head --sql
```

## 接口范围

当前对外接口主要包括：

- `GET /health`
- `POST /api/v1/chat`
- `POST /api/v1/chat/stream`
- `POST /api/v1/chat/resume`
- `GET /api/v1/chat/sessions/{session_id}`
- `POST /api/v1/ingest/post`
- `POST /api/v1/ingest/rebuild`
- `GET /api/v1/ingest/jobs/{job_id}`

完整契约：

- `specs/001-fastapi-rag-backend/contracts/openapi.yaml`

## 当前实现的重要说明

### 1. 流式接口当前是伪流式

- 后端先拿完整回答
- 再拆成 SSE 事件输出

### 2. 同步接口当前仍是请求内执行

- 接口返回 `202`
- 但当前还没有真正拆到异步任务队列

### 3. 图级 checkpoint 当前使用内存保存器

- `LangGraph` 运行时 checkpoint 在进程重启后不会保留
- 但业务消息、会话摘要和会话状态仍会写入 PostgreSQL

## 与 `geminiBlog` 的关系

当前博客前端接入点：

- `E:\code\geminiBlog\src\components\chat-bot.tsx`

推荐接入顺序：

1. 先接 `POST /api/v1/chat`
2. 再接 `POST /api/v1/chat/stream`
3. 最后补 `session_id` 持久化和会话恢复

详细说明见：

- `docs/integration/geminiblog-chatbot.md`

## 旧 Demo 与实验文件

仓库里仍保留了一部分旧的 CLI / 实验文件，但现在已经统一归档到 `legacy/cli_demo/`，例如：

- `legacy/cli_demo/multi_functional_chain.py`
- `legacy/cli_demo/rag_graph.py`
- `legacy/cli_demo/eval_rag.py`
- `legacy/README.md`

根目录 `main.py` 现在只是迁移期入口：

- 默认提示使用 FastAPI 主线
- 只有显式传入 `--legacy-cli` 时才会加载 `legacy/cli_demo/` 中的旧版脚本

这些文件当前主要用于历史参考、评估或迁移过渡，不再是对外 FastAPI 后端的主入口。
