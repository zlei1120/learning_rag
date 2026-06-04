# 快速开始：FastAPI RAG 后端

## 说明

本文件描述的是本期实现完成后的预期使用方式，用于指导维护者和联调人员快速跑通本地环境。

当前改造仓库：

- `D:\code\learning_rag`

关联博客项目：

- `E:\code\geminiBlog`

## 一、准备条件

### 1. 必备环境

- Python 3.12
- `uv`
- PostgreSQL 16
- `pgvector` 扩展
- 可用的百炼平台访问凭据

### 2. 需要能访问博客数据库

文章真源来自：

- `E:\code\geminiBlog` 对应的 PostgreSQL

如果本地用博客项目自带的数据库容器，可在博客项目目录执行：

```powershell
Set-Location E:\code\geminiBlog
docker compose up -d db
```

## 二、数据库准备

### 1. 确认博客库可访问

你需要能连接到 `geminiBlog` 使用的数据库，并读取 `Post` 表。

### 2. 开启 `pgvector`

连接目标数据库后执行：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3. 建议准备独立 schema

建议把 RAG 索引表放到独立 schema，例如：

```sql
CREATE SCHEMA IF NOT EXISTS rag;
```

这样便于和博客业务表隔离。

## 三、环境变量

建议在 `D:\code\learning_rag` 下准备 `.env`。

示例：

```env
DATABASE_URL=postgresql+psycopg://blog:blog_password@127.0.0.1:5432/blog

OPENAI_API_KEY=你的百炼Key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
BLOG_PUBLIC_BASE_URL=https://你的博客域名

CHAT_MODEL=qwen3.6-plus
EMBEDDING_MODEL=text-embedding-v4
RERANK_MODEL=qwen3-rerank
OCR_MODEL=qwen-vl-ocr-latest
IMAGE_CAPTION_MODEL=qwen-vl-plus

CHAT_CONTEXT_MAX_TOKENS=24000
CHAT_CONTEXT_RECENT_MESSAGES_TOKENS=3000
CHAT_CONTEXT_SUMMARY_TOKENS=2000
CHAT_CONTEXT_RETRIEVAL_TOKENS=12000
CHAT_CONTEXT_IMAGE_TOKENS=4000
CHAT_CONTEXT_RESERVED_OUTPUT_TOKENS=3000

CHAT_RETRIEVAL_TOP_K=8
CHAT_IMAGE_TOP_K=3
CHAT_ENABLE_PARENT_CHUNK_EXPANSION=true

IMAGE_FETCH_TIMEOUT_SECONDS=20
IMAGE_OCR_MIN_PIXELS=3072
IMAGE_OCR_MAX_PIXELS=8388608
```

说明：

- `OPENAI_BASE_URL` 未配置或为空时，后端默认使用百炼 OpenAI 兼容地址
- `BLOG_PUBLIC_BASE_URL` 用于把 `/uploads/...` 这类博客图片相对路径拼成可访问地址
- 上下文预算参数是本期的关键调优项

## 四、安装依赖

在 `D:\code\learning_rag` 下执行：

```powershell
uv sync
```

如果后续项目仍保留 `pyproject.toml` 驱动，这将是默认安装方式。

## 五、启动服务

预期启动命令：

```powershell
uv run uvicorn app.main:app --reload
```

预期默认地址：

```text
http://127.0.0.1:8000
```

健康检查：

```powershell
Invoke-RestMethod -Method GET -Uri http://127.0.0.1:8000/health
```

## 六、同步文章

### 1. 单篇同步

预期接口：

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://127.0.0.1:8000/api/v1/ingest/post `
  -ContentType "application/json" `
  -Body '{"slug":"hello-nextjs"}'
```

预期用途：

- 当博客后台保存单篇文章后，可触发同步这一篇

### 2. 全量重建

预期接口：

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://127.0.0.1:8000/api/v1/ingest/rebuild `
  -ContentType "application/json" `
  -Body '{"scope":"all"}'
```

适用场景：

- 首次建库
- 大规模模型切换
- 索引结构升级

### 3. 查询任务状态

预期接口：

```powershell
Invoke-RestMethod `
  -Method GET `
  -Uri http://127.0.0.1:8000/api/v1/ingest/jobs/{job_id}
```

## 七、验证单轮问答

预期接口：

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://127.0.0.1:8000/api/v1/chat `
  -ContentType "application/json" `
  -Body '{
    "session_id":"demo-session-1",
    "message":"这个博客里关于 RAG 的文章主要讲了什么？"
  }'
```

预期响应至少包含：

- `answer`
- `session_id`
- `sources`
- `related_images`

## 八、验证多轮会话

### 第一轮

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://127.0.0.1:8000/api/v1/chat `
  -ContentType "application/json" `
  -Body '{
    "session_id":"demo-session-2",
    "message":"数据库配置那篇教程的主要步骤是什么？"
  }'
```

### 第二轮追问

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://127.0.0.1:8000/api/v1/chat `
  -ContentType "application/json" `
  -Body '{
    "session_id":"demo-session-2",
    "message":"第二步里的端口是什么意思？"
  }'
```

预期结果：

- 第二轮能结合第一轮上下文理解“第二步”
- 如果换一个新的 `session_id`，则不应继承旧上下文

## 九、查看会话状态

预期接口：

```powershell
Invoke-RestMethod `
  -Method GET `
  -Uri http://127.0.0.1:8000/api/v1/chat/sessions/demo-session-2
```

预期用途：

- 查看会话元数据
- 验证会话隔离是否正常

## 十、上下文预算调试

本项目的一个核心点是：不能让检索文本、OCR 文本和历史消息无限膨胀。

建议至少调试这些参数：

- `CHAT_CONTEXT_MAX_TOKENS`
- `CHAT_CONTEXT_RECENT_MESSAGES_TOKENS`
- `CHAT_CONTEXT_SUMMARY_TOKENS`
- `CHAT_CONTEXT_RETRIEVAL_TOKENS`
- `CHAT_CONTEXT_IMAGE_TOKENS`
- `CHAT_CONTEXT_RESERVED_OUTPUT_TOKENS`

观察重点：

- 回答是否变短或丢失细节
- 图片相关问题是否还能答上来
- 多轮对话是否还能保持连续性
- 延迟和成本是否明显失控

## 十一、和 `geminiBlog` 联调

前端接入点：

- `E:\code\geminiBlog\src\components\chat-bot.tsx`

联调重点：

- 保存并复用 `session_id`
- 将 Mock 请求替换成真实 HTTP 请求
- 展示来源片段
- 展示相关图片
- 处理超时、失败和限流状态

## 十二、排错建议

### 1. 没有召回到文章内容

优先检查：

- 文章是否 `published=true`
- 是否已完成同步
- `rag_documents / rag_chunks / rag_embeddings` 是否有对应数据

### 2. 图片问题答不上来

优先检查：

- `rag_images` 是否已提取到图片
- `rag_image_features` 是否有 OCR / caption 结果
- 图片文本是否因为预算太紧被裁掉

### 3. 多轮会话串话

优先检查：

- 是否错误复用了 `session_id`
- `chat_sessions / chat_messages / memory_records` 是否带作用域过滤

### 4. 上下文溢出或成本过高

优先检查：

- 检索 `top_k`
- OCR 文本长度
- 最近消息保留长度
- 摘要记忆长度

## 十三、当前阶段的重要说明

本期快速开始遵循以下明确约束：

- 直接用 `LangGraph`
- 先不用 `mem0`
- 所有人不共用同一套会话记忆
- 共享的是知识库，不共享的是会话历史
- 上下文预算必须作为正式调优对象，而不是实现细节
