# 配置说明

## 配置入口

当前运行时配置定义位于：

- `app/core/config.py`

环境变量默认从以下位置读取：

- `.env`

编码约定：

- UTF-8

## 一、基础服务配置

### `APP_NAME`

- 默认值：`learning-rag-api`
- 用途：FastAPI 服务名、健康检查返回值

### `APP_VERSION`

- 默认值：`0.1.0`
- 用途：接口版本展示和运维对齐

### `DEBUG`

- 默认值：`false`
- 支持值：`true / false / 1 / 0 / development / production` 等

## 二、数据库配置

### `DATABASE_URL`

- 默认值：`postgresql+psycopg://blog:blog_password@127.0.0.1:5432/blog`
- 用途：连接 `geminiBlog` 所在 PostgreSQL

注意：

- 如果密码里有 `@`、`:`、`/` 这类特殊字符，必须先做 URL 编码
- 例如 `password@123` 要写成 `password%40123`
- 你当前这类“本地通过 SSH 隧道连云上博客库”的场景，常见写法就是 `127.0.0.1:5433`
- 如果 SSH 命令是 `ssh -N -L 5433:127.0.0.1:5432 ubuntu@服务器地址`，这里就应该写本地端口 `5433`，而不是远端 PostgreSQL 的 `5432`
- `.env` 修改后，已经运行中的 `uvicorn` 进程不会自动刷新配置，建议重启服务后再验证 `/health`

### `RAG_SCHEMA`

- 默认值：`rag`
- 用途：把 RAG 相关表隔离到独立 schema

### 推荐做法

- 博客业务表和 RAG 表继续共用一个 PostgreSQL 实例
- 但用独立 schema 隔离 RAG 索引
- 如果博客库来自 `E:\code\geminiBlog\docker-compose.yml`，要确认该库已经启用了 `pgvector`

## 三、百炼与模型配置

### `OPENAI_API_KEY`

- 用途：百炼 OpenAI 兼容接口访问凭据

### `OPENAI_BASE_URL`

- 默认值：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- 说明：为空时会自动回退到这个默认值

### `RERANK_BASE_URL`

- 默认值：`https://dashscope.aliyuncs.com/compatible-api/v1`
- 用途：百炼 rerank 接口

### `CHAT_MODEL`

- 默认值：`qwen3.6-plus`

### `EMBEDDING_MODEL`

- 默认值：`text-embedding-v4`

### `RERANK_MODEL`

- 默认值：`qwen3-rerank`

### `OCR_MODEL`

- 默认值：`qwen-vl-ocr-latest`

### `IMAGE_CAPTION_MODEL`

- 默认值：`qwen-vl-plus`

## 四、博客图片访问配置

### `BLOG_PUBLIC_BASE_URL`

- 默认值：空
- 用途：把文章中的相对图片地址，例如 `/uploads/...`，拼成模型可访问的绝对地址

### 为什么它重要

当前图片理解链路会先尝试下载图片再转成 Data URL 给模型。

如果文章里写的是：

- `/uploads/tutorial/a.png`

而你没有配置 `BLOG_PUBLIC_BASE_URL`，后端就无法解析成可访问绝对地址。

## 五、问答相关配置

### 1. 召回与上下文规模

- `CHAT_RETRIEVAL_TOP_K`
  文本召回后保留的候选数

- `CHAT_IMAGE_TOP_K`
  图片文本特征候选数

- `CHAT_ENABLE_PARENT_CHUNK_EXPANSION`
  是否在命中 chunk 周围补相邻内容

- `CHAT_PARENT_CHUNK_WINDOW_SIZE`
  每侧补多少个相邻 chunk

### 2. 最近消息与摘要

- `CHAT_HISTORY_MESSAGE_LIMIT`
  最近消息窗口的最大条数

- `CHAT_SUMMARY_MAX_CHARS`
  摘要记忆最大长度

### 3. 上下文预算

- `CHAT_CONTEXT_MAX_TOKENS`
- `CHAT_CONTEXT_RECENT_MESSAGES_TOKENS`
- `CHAT_CONTEXT_SUMMARY_TOKENS`
- `CHAT_CONTEXT_RETRIEVAL_TOKENS`
- `CHAT_CONTEXT_IMAGE_TOKENS`
- `CHAT_CONTEXT_RESERVED_OUTPUT_TOKENS`

上下文预算默认值和调优建议另见：

- `docs/backend/context-budget.md`

### 调参建议

- 如果教程截图问题经常答不上来，先看 `CHAT_CONTEXT_IMAGE_TOKENS`
- 如果多轮追问经常丢上下文，先看 `CHAT_CONTEXT_RECENT_MESSAGES_TOKENS`
- 如果命中文本多但回答仍然片段化，先看 `CHAT_RETRIEVAL_TOP_K` 和 `CHAT_PARENT_CHUNK_WINDOW_SIZE`

## 六、同步相关配置

- `INGEST_CHUNK_SIZE`
  Markdown 文本切块长度

- `INGEST_CHUNK_OVERLAP`
  chunk 重叠长度

- `INGEST_IMAGE_CONTEXT_WINDOW`
  提取图片前后文时保留的字符窗口

- `EMBEDDING_BATCH_SIZE`
  文本向量批处理大小

说明：

- 当前百炼 `text-embedding-v4` 按单次最多 `10` 条输入处理
- 项目默认值已经调整为 `10`
- 即使环境变量误配成更大，运行时也会自动压到 `10`

## 七、图片 OCR 配置

- `IMAGE_FETCH_TIMEOUT_SECONDS`
  下载图片超时时间

- `IMAGE_OCR_MIN_PIXELS`
- `IMAGE_OCR_MAX_PIXELS`
  OCR 调用时传给模型的像素上下限

## 八、本地开发与回退行为

当前代码对“没有百炼 Key”的本地开发做了可运行兜底：

- 文本 embedding 会生成稳定的本地占位向量
- rerank 会回退到基于原始分数和关键词命中的排序
- 问答生成会回退到本地拼装回答
- 图片理解会生成启发式回退说明

这意味着：

- 没有真实模型 Key 时，链路仍可跑通
- 但回答质量、OCR 质量和 rerank 效果不能代表线上表现

## 九、推荐 `.env` 示例

```env
APP_NAME=learning-rag-api
APP_VERSION=0.1.0
DEBUG=false

DATABASE_URL=postgresql+psycopg://blog:blog_password@127.0.0.1:5432/blog
RAG_SCHEMA=rag

OPENAI_API_KEY=你的百炼Key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
RERANK_BASE_URL=https://dashscope.aliyuncs.com/compatible-api/v1
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
CHAT_HISTORY_MESSAGE_LIMIT=8
CHAT_SUMMARY_MAX_CHARS=600

CHAT_RETRIEVAL_TOP_K=8
CHAT_IMAGE_TOP_K=3
CHAT_ENABLE_PARENT_CHUNK_EXPANSION=true
CHAT_PARENT_CHUNK_WINDOW_SIZE=2

INGEST_CHUNK_SIZE=900
INGEST_CHUNK_OVERLAP=120
INGEST_IMAGE_CONTEXT_WINDOW=220
EMBEDDING_BATCH_SIZE=10

IMAGE_FETCH_TIMEOUT_SECONDS=20
IMAGE_OCR_MIN_PIXELS=3072
IMAGE_OCR_MAX_PIXELS=8388608
```

如果通过 SSH 隧道连接云上博客库，例如本地监听 `5433`：

```env
DATABASE_URL=postgresql+psycopg://blog:真实密码@127.0.0.1:5433/blog
```

## 十、安全建议

- `.env` 不要提交到仓库
- 不要把私有 GitHub 仓库的带鉴权地址直接写入对外博客正文
- 生产环境建议单独管理数据库凭据和百炼 Key
- 如果后续加入真正的用户体系，再把 `user_key` 与认证体系打通
