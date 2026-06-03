# 实施计划：将 `learning_rag` 改造成标准 FastAPI RAG 后端

**分支**：`001-fastapi-rag-backend` | **日期**：`2026-06-03` | **规格说明**：[spec.md](d:\code\learning_rag\specs\001-fastapi-rag-backend\spec.md)

**输入**：来自 `D:\code\learning_rag\specs\001-fastapi-rag-backend\spec.md` 的功能规格说明

## 概要

本期目标是把当前以 CLI demo 为主的 `learning_rag` 改造成一个可长期维护的 FastAPI 后端服务，对接 `E:\code\geminiBlog` 的 PostgreSQL 博客真源，为博客问答弹窗提供正式的文章问答能力。

技术路线如下：

- 保留当前仓库中已有的 Markdown 标题切分、语义分块、多路检索和重排思路。
- 移除“启动即清库、从本地 `data/` 目录读文件”的 demo 主流程，改为 FastAPI 服务化架构。
- 以 `geminiBlog` 的 PostgreSQL `Post` 表为文章真源，建立独立的 RAG 索引表或独立 schema。
- 使用 `pgvector` 存储文本向量，使用百炼平台完成文本 embedding、rerank、图片 OCR 与图片说明生成。
- 直接以 `LangGraph` 作为核心编排层，承担检索流程、多轮会话、记忆恢复、上下文预算控制和可扩展的中断/恢复能力。
- 将图片 OCR 文本、图片说明和邻近正文一起纳入召回链路，而不是只把图片当作静态资源。
- 将多轮会话、短期记忆和上下文预算控制作为正式架构约束，从一开始就考虑会话状态持久化、历史裁剪与摘要记忆。
- 核心架构不建立在高层 `LangChain` chain 抽象之上，而是在 `LangGraph` 之上组织本项目自己的数据层、服务层和 API 层，同时保留后续接入 Deep Agents 一类 agent harness 的适配边界。
- 一期不引入 `mem0`，记忆能力先由 `LangGraph` 状态管理与本项目自定义会话/记忆持久化结构承担。
- 输出完整中文交付物，包括：
  - 面向前端的 API 文档
  - 面向维护者的开发文档
  - 面向 `geminiBlog` 的接入文档

## 技术上下文

**语言/版本**：Python 3.12

**主要依赖**：

- FastAPI
- Uvicorn
- Pydantic
- SQLAlchemy 或 SQLModel（待设计阶段最终确认）
- psycopg
- pgvector
- LangGraph
- loguru
- pytest
- 百炼平台 OpenAI 兼容接口或等价官方 SDK

**存储**：

- 主数据源：`E:\code\geminiBlog` 对应的 PostgreSQL `Post` 表
- RAG 索引存储：同一 PostgreSQL 中新增的 RAG 表或独立 schema
- 向量存储：PostgreSQL `pgvector`
- 图片原始资源：沿用 `geminiBlog` 当前 GitHub 私有仓库存储 + Next.js 图片代理链路

**测试**：

- `pytest`
- FastAPI `TestClient`
- 同步流程集成测试
- 数据库集成测试
- 合同测试/接口结构测试

**目标平台**：

- 本地 Windows 开发环境
- 云端 Linux 服务环境
- Docker / 容器化部署环境

**项目类型**：独立后端 Web 服务

**性能目标**：

- 单篇文章同步应支持增量更新，不依赖全量重建
- 普通博客问答在当前文章规模下应达到可交互延迟
- 首版优先保证正确性、可维护性和可观测性，再逐步优化极限性能

**约束条件**：

- 不能依赖 CLI `input()` 交互
- 不能在服务启动时清空索引或重建全部向量
- 不能公开召回未发布文章
- 必须考虑图片语义缺失问题
- 必须考虑多轮问答的会话状态和记忆持久化
- 必须控制上下文窗口占用，避免随着检索结果、OCR 文本和会话历史增长而失控
- 必须交付详细中文文档，而不是只交付代码

**规模/范围**：

- 当前文章约 24 篇，且更新频率较高
- 文章内容以 Markdown 为主，包含图片、教程步骤、代码块和结构化标题
- 前端消费方为 `E:\code\geminiBlog\src\components\chat-bot.tsx`

## 方案校验

### 校验结果

- 当前方案符合“先从现有编排层演进，而不是重写底层组件”的仓库现状。
- 当前方案符合“使用 PostgreSQL 作为正式数据库，而不是继续围绕 SQLite 或临时文件方案优化”的用户方向。
- 当前方案明确要求中文 API 文档、开发文档和博客接入文档，满足本期交付要求。
- 当前方案未引入额外前端项目，也未要求改造 `geminiBlog` 为后端宿主，职责边界清晰。
- 当前方案已将 `LangGraph`、多轮会话、记忆持久化、上下文大小控制和后续 agent harness 扩展纳入架构边界，避免后补时推翻主结构。
- 当前方案已明确一期不引入 `mem0`，避免在外部记忆中台与当前会话设计之间制造额外耦合。

### 当前阶段结论

可以进入后续设计与任务拆分阶段，无需因架构方向重做规格。

## 项目结构

### 本功能文档结构

```text
specs/001-fastapi-rag-backend/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### 目标源码结构

```text
D:\code\learning_rag\
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── deps.py
│   │   ├── routes/
│   │   │   ├── health.py
│   │   │   ├── chat.py
│   │   │   ├── ingest.py
│   │   │   └── admin.py
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── database.py
│   │   └── lifecycle.py
│   ├── schemas/
│   │   ├── common.py
│   │   ├── chat.py
│   │   ├── ingest.py
│   │   └── document.py
│   ├── repositories/
│   │   ├── blog_post_repository.py
│   │   ├── rag_document_repository.py
│   │   ├── rag_chunk_repository.py
│   │   ├── rag_image_repository.py
│   │   ├── session_repository.py
│   │   ├── memory_repository.py
│   │   └── ingest_job_repository.py
│   ├── services/
│   │   ├── blog_source_service.py
│   │   ├── markdown_ingest_service.py
│   │   ├── embedding_service.py
│   │   ├── rerank_service.py
│   │   ├── image_understanding_service.py
│   │   ├── graph_runtime_service.py
│   │   ├── context_budget_service.py
│   │   ├── session_service.py
│   │   ├── memory_service.py
│   │   ├── retrieval_service.py
│   │   ├── answer_service.py
│   │   ├── ingest_service.py
│   │   └── chat_service.py
│   ├── models/
│   │   ├── rag_document.py
│   │   ├── rag_chunk.py
│   │   ├── rag_embedding.py
│   │   ├── rag_image.py
│   │   ├── chat_session.py
│   │   ├── chat_message.py
│   │   ├── memory_record.py
│   │   └── ingest_job.py
│   └── utils/
│       ├── markdown.py
│       ├── hashing.py
│       └── time.py
├── migrations/
├── docs/
│   ├── api/
│   ├── backend/
│   ├── integration/
│   └── troubleshooting/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── contract/
├── scripts/
│   ├── sync_single_post.py
│   ├── sync_all_posts.py
│   └── rebuild_embeddings.py
└── legacy/
    └── （迁移期保留的旧 demo 文件，按需逐步收敛）
```

**结构决策**：

- 采用标准 FastAPI 后端结构，而不是继续以扁平脚本文件为主。
- 将“API 层、服务层、仓储层、数据模型层、文档层”明确拆开，便于长期维护。
- 现有 `chunker.py`、`markdown_chunker.py`、`multi_functional_chain.py` 等逻辑将择机迁移到 `app/services` 或 `app/utils` 下，而不是继续直接作为顶层脚本入口。
- `geminiBlog` 不是本仓库的子目录，不会纳入本项目代码树；它作为外部集成方通过文档和接口契约接入。
- 会话、记忆、上下文预算单独建模，由 `LangGraph` 负责编排运行时状态；未来若接入 Deep Agents，也优先复用这些持久化结构和服务接口。

## 集成对象与边界

### 外部集成项目

```text
E:\code\geminiBlog
├── prisma\schema.prisma
├── src\lib\posts-db.ts
├── src\app\api\admin\posts\route.ts
├── src\components\chat-bot.tsx
├── src\app\api\admin\uploads\route.ts
└── src\app\uploads\[...path]\route.ts
```

### 职责边界

- `learning_rag`：
  - 提供 FastAPI RAG 服务
  - 执行文章同步、分块、向量化、重排、OCR、图片说明生成
  - 提供问答与同步 API
  - 提供文档和测试

- `geminiBlog`：
  - 继续作为博客内容管理与展示系统
  - 继续持有文章真源 `Post` 表
  - 继续处理编辑器、文章保存、图片上传、图片代理展示
  - 通过 HTTP 调用 `learning_rag` 的后端接口

## 设计阶段输出物

### 1. research.md

需要沉淀的内容：

- 百炼平台模型选型与调用形态
- `pgvector` 在当前文章规模下的使用策略
- 文本召回 + 图片 OCR/caption 增强召回的组合方式
- 增量同步策略和内容哈希策略
- FastAPI 生命周期与后台任务方案
- LangGraph 的 checkpoint / persistence 设计
- 多轮会话记忆策略
- 上下文预算分配与裁剪策略
- 后续接入 Deep Agents 时如何复用当前 `LangGraph` 之上的数据结构和 API 契约
- 为什么一期不引入 `mem0`，以及未来若接入外部记忆中台时的迁移边界

### 2. data-model.md

需要明确的内容：

- RAG 新增表结构
- 表之间的主外键关系
- 文档、chunk、embedding、图片、任务的状态模型
- 向量版本、图片处理状态、同步状态
- 会话线程、会话消息、记忆记录和上下文预算策略的数据结构

### 3. contracts/

需要定义的接口契约：

- `GET /health`
- `POST /api/v1/chat`
- `POST /api/v1/chat/stream` 或等价流式接口
- `POST /api/v1/chat/resume`（如使用中断/恢复语义）
- `POST /api/v1/ingest/post`
- `POST /api/v1/ingest/rebuild`
- `GET /api/v1/ingest/jobs/{job_id}`
- `GET /api/v1/chat/sessions/{session_id}`

### 4. quickstart.md

需要面向维护者说明：

- 本地环境准备
- PostgreSQL 与 `pgvector` 准备
- 百炼环境变量配置
- 本地启动
- 单篇同步
- 全量同步
- 问答接口验证
- 多轮会话验证
- 上下文预算调试方式

## 数据设计方向

### 数据源表

复用 `geminiBlog` 的：

- `Post`
  - 关键字段：`id`、`slug`、`title`、`content`、`published`、`tags`、`date`、`updatedAt`

### 新增 RAG 索引表建议

- `rag_documents`
  - 对应一篇文章的索引主记录
  - 存文章主键映射、slug、标题、内容哈希、published 状态、最后同步时间

- `rag_chunks`
  - 存正文 chunk
  - 包含 `title_path`、`section_id`、`chunk_index`、`chunk_hash`、正文内容、邻近上下文

- `rag_embeddings`
  - 存文本向量
  - 包含 `chunk_id`、向量值、模型名、维度、版本、更新时间

- `rag_images`
  - 存文章中的图片
  - 包含图片 URL、alt、原始 Markdown、所在 section、邻近文本、处理状态

- `rag_image_features`
  - 存 OCR 文本、caption 文本、图片语义摘要
  - 用于参与文本召回

- `rag_chunk_images`
  - 建立 chunk 和图片的关联

- `rag_ingest_jobs`
  - 存同步任务
  - 支持单篇同步、批量同步、重建任务

- `chat_sessions`
  - 存多轮会话线程
  - 记录会话标识、状态、摘要、最近访问时间

- `chat_messages`
  - 存多轮对话消息
  - 记录角色、内容、引用来源、裁剪状态

- `memory_records`
  - 存短期摘要记忆或可扩展长期记忆
  - 供多轮问答和未来 agent 编排复用

### 数据策略要点

- 以 `content_hash` 控制文章级增量同步
- 以 `chunk_hash` 控制 chunk 级重建
- 以图片内容标识或 URL + 邻近上下文控制图片重复处理
- 图片 OCR / caption 结果单独持久化，避免重复调用模型
- 以 `session_id` 管理多轮上下文
- 对历史消息、检索片段、图片文本和摘要记忆分别做预算控制
- `LangGraph` 的运行状态与业务会话状态分层设计，避免图运行时状态和对外 API 会话语义混淆

## 核心链路设计

### 一、文章同步链路

1. 从 PostgreSQL 读取已发布文章
2. 将文章内容转成内部 `Document` 对象
3. 按 Markdown 标题切 section
4. 对超长 section 做二次语义切分
5. 提取图片引用、alt、邻近正文
6. 对文本 chunk 执行 embedding
7. 对图片执行 OCR / caption
8. 持久化 chunk、向量、图片和任务状态

### 二、问答链路

1. 接收博客前端问题
2. 读取或创建会话线程
3. 恢复最近轮消息和可用摘要记忆
4. 将请求送入 `LangGraph` 图运行时
5. 在图节点中执行查询改写、检索、图片文本召回、重排、上下文裁剪和回答生成
6. 必要时通过图状态执行中断/恢复或多阶段决策
7. 更新消息历史、会话摘要和图状态持久化
8. 返回回答、来源、相关图片和会话信息

### 三、博客端接入链路

1. `geminiBlog` 的 `chat-bot.tsx` 发起请求
2. FastAPI 返回标准 JSON 或流式响应
3. 前端展示回答正文
4. 前端展示来源文章与片段
5. 前端展示相关图片或图片引用
6. 前端处理超时、限流、失败提示

## 文档交付计划

本期文档不是附属物，而是主交付内容之一。必须在实现阶段同步完成。

### API 文档

输出位置建议：

```text
docs/api/
├── overview.md
├── health.md
├── chat.md
├── ingest.md
└── error-handling.md
```

文档内容至少包括：

- 接口用途
- 请求头与鉴权方式
- 请求体字段
- 响应体字段
- `session_id`、消息历史、上下文预算相关字段
- 来源字段说明
- 图片字段说明
- 错误码
- 示例请求与示例响应
- 流式接口说明

### 开发文档

输出位置建议：

```text
docs/backend/
├── architecture.md
├── configuration.md
├── data-flow.md
├── indexing.md
├── models-and-services.md
└── deployment.md
```

文档内容至少包括：

- 项目目录结构
- 模块职责
- 同步链路
- 问答链路
- 会话与记忆链路
- 上下文预算控制策略
- 模型接入
- 数据表说明
- 本地与云端部署步骤

### 博客端接入文档

输出位置建议：

```text
docs/integration/
└── geminiblog-chatbot.md
```

文档内容至少包括：

- `E:\code\geminiBlog\src\components\chat-bot.tsx` 当前现状
- 如何替换 Mock 请求
- 如何处理流式输出
- 如何维护 `session_id`
- 如何展示来源和图片
- 如何处理错误和重试
- 如何区分“无答案”“服务失败”“被限流”

### 排错文档

输出位置建议：

```text
docs/troubleshooting/
├── database.md
├── embeddings.md
├── ocr-and-images.md
└── api-debugging.md
```

## 实施阶段划分

### 阶段 0：确认与研究

- 确认百炼模型接法
- 确认 `pgvector` 使用方式
- 确认本仓库的迁移边界
- 确认多轮记忆与上下文预算方案
- 确认未来 agent harness 适配边界
- 输出 `research.md`

### 阶段 1：结构改造与基础设施

- 建立 FastAPI 项目结构
- 建立配置、日志、数据库连接
- 建立基础模型与仓储层
- 建立健康检查接口

### 阶段 2：文章同步链路

- 接入 `geminiBlog` PostgreSQL 真源
- 实现文章读取和内部文档转换
- 实现 Markdown 分块迁移
- 实现 RAG 索引表写入
- 实现单篇/全量同步

### 阶段 3：图片理解增强

- 图片提取
- OCR 集成
- caption 集成
- 图片文本特征持久化
- 图片与 chunk 关联

### 阶段 4：问答接口

- 检索链路
- rerank
- 会话状态恢复
- 历史消息持久化
- 上下文预算控制
- 摘要记忆生成
- 回答生成
- 来源与图片返回结构
- 流式输出

### 阶段 5：文档与测试

- API 文档
- 开发文档
- 博客端接入文档
- 单元测试
- 集成测试
- 合同测试

## 测试策略

### 单元测试

- Markdown 分块
- 标题路径构建
- 内容哈希计算
- 图片提取
- 响应结构格式化
- 上下文预算分配
- 历史消息裁剪
- 记忆摘要生成
- LangGraph 节点输入输出映射

### 集成测试

- 从 PostgreSQL 读取文章并完成同步
- 单篇文章更新后的增量重建
- 已隐藏文章不参与召回
- 问答接口返回来源和图片
- 多轮问答中的会话连续性
- 长上下文场景下的预算控制
- LangGraph 持久化状态恢复

### 合同测试

- `chat` 接口字段契约
- `ingest` 接口字段契约
- 错误结构契约
- 博客端需要依赖的流式格式契约
- 会话字段和上下文预算字段契约
- `resume` 接口或等价恢复接口契约

## 风险与缓解

| 风险 | 影响 | 缓解方式 |
|---|---|---|
| `pgvector` 在线上环境不可用 | 无法落地向量检索 | 在实施早期优先验证扩展安装与连接能力 |
| 图片 OCR 成本或延迟过高 | 同步速度下降 | 先做增量处理、结果缓存和状态持久化 |
| 当前中文关键词检索不足 | 教程问法召回不稳定 | 首期以向量召回 + rerank 为主，后续再增强关键词检索 |
| 文档滞后于实现 | 前后端联调困难 | 将文档交付列为硬性完成条件，与代码同步提交 |
| `geminiBlog` 后续字段变化 | 同步链路失效 | 在仓储层隔离外部数据结构，减少直接耦合 |
| 多轮历史和 OCR 文本导致上下文膨胀 | 成本飙升、超出窗口、回答变慢 | 引入预算服务、历史裁剪、摘要压缩和字段级限额 |
| LangGraph 运行状态与业务会话状态耦合过深 | 后续维护和扩展困难 | 在数据设计时区分业务会话、记忆记录和图持久化状态 |
| 后续接 agent 框架时现有实现难以复用 | 再次大规模重构 | 以当前持久化数据结构和 API 契约为边界，Deep Agents 仅作为上层适配 |
| 过早引入外部记忆中台导致复杂度上升 | 设计发散、调试成本增加 | 一期先用 LangGraph + 自定义持久化结构跑通，后续再评估 mem0 一类方案 |

## 复杂度跟踪

当前无需记录额外架构违规项。

本期引入的分层、仓储和独立索引表并非过度设计，而是因为：

- 目标已从本地 demo 变成独立服务
- 数据源来自外部博客项目
- 需要长期维护和跨仓库联调
- 文本、图片、同步任务和 API 文档都需要清晰边界
