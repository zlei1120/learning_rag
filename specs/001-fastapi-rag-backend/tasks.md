# 任务清单：将 `learning_rag` 改造成标准 FastAPI RAG 后端

**输入**：来自 `specs/001-fastapi-rag-backend/` 下的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/openapi.yaml`

**前置文档**：

- `spec.md`
- `plan.md`
- `research.md`
- `data-model.md`
- `contracts/openapi.yaml`

**测试要求**：本期必须包含自动化测试，至少覆盖同步流程、问答接口、多轮会话、图文召回和关键错误场景。

## 格式说明

- `[P]` 表示可并行执行
- `[US1]` 到 `[US5]` 对应 `spec.md` 中的用户故事
- 每条任务尽量指向明确文件路径

## Phase 1：项目初始化与目录搭建

**目标**：把当前 demo 仓库拉到可实现 FastAPI 服务的基本结构

- [x] T001 创建 `app/`、`tests/`、`docs/`、`scripts/` 基础目录结构
- [x] T002 调整 [pyproject.toml](d:\code\learning_rag\pyproject.toml) 依赖，加入 FastAPI、Uvicorn、LangGraph、SQLAlchemy/SQLModel、psycopg、pgvector、pytest 等正式依赖
- [x] T003 [P] 新建 `app/main.py`、`app/core/config.py`、`app/core/logging.py`、`app/core/database.py`
- [x] T004 [P] 新建 `app/api/routes/health.py`、`app/api/routes/chat.py`、`app/api/routes/ingest.py`
- [x] T005 [P] 新建 `tests/unit/`、`tests/integration/`、`tests/contract/` 目录占位

---

## Phase 2：基础设施与阻塞项

**目标**：在任何用户故事开始前，先把所有共用底座搭好

**关键说明**：这一阶段完成前，不建议开始具体业务实现。

- [ ] T006 建立数据库基础模型与迁移框架，新增 `app/models/` 和 `migrations/`
- [x] T007 [P] 新建 `app/schemas/common.py`、`app/schemas/chat.py`、`app/schemas/ingest.py`
- [x] T008 [P] 新建统一异常模型和错误处理逻辑到 `app/api/deps.py` 或等价错误处理中间件
- [ ] T009 [P] 新建结构化日志与请求链路日志
- [x] T010 建立 `LangGraph` 运行时封装入口到 `app/services/orchestration_service.py`
- [x] T011 建立上下文预算配置模型和预算控制服务到 `app/services/context_budget_service.py`
- [x] T012 建立会话隔离基础约定：`session_id` 生成、读取、校验规则

**检查点**：完成后，项目应具备启动 FastAPI、连接数据库、加载配置和返回统一错误结构的能力。

---

## Phase 3：用户故事 1 - 同步博客文章并建立可检索知识库（P1）🎯 MVP

**目标**：能从 `geminiBlog` 的 PostgreSQL 真源同步文章，并生成 RAG 索引

**独立验证**：创建或修改一篇 `published=true` 的文章后，可以通过同步接口生成/更新 `rag_documents`、`rag_chunks`、`rag_embeddings`、`rag_images`、`rag_image_features`

### 测试

- [ ] T013 [P] [US1] 为同步接口编写合同测试：`tests/contract/test_ingest_api.py`
- [ ] T014 [P] [US1] 为单篇文章同步编写集成测试：`tests/integration/test_ingest_single_post.py`
- [ ] T015 [P] [US1] 为 Markdown 标题切分与图片提取编写单元测试：`tests/unit/test_markdown_ingest.py`

### 实现

- [x] T016 [US1] 新建 `app/repositories/blog_post_repository.py`，从 `geminiBlog` 的 `Post` 表读取文章
- [x] T017 [P] [US1] 新建 `app/models/rag_document.py`、`app/models/rag_chunk.py`、`app/models/rag_embedding.py`
- [x] T018 [P] [US1] 新建 `app/models/rag_image.py`、`app/models/ingest_job.py`
- [ ] T019 [P] [US1] 新建 `app/repositories/rag_document_repository.py`、`app/repositories/rag_chunk_repository.py`
- [ ] T020 [P] [US1] 新建 `app/repositories/rag_image_repository.py`、`app/repositories/ingest_job_repository.py`
- [ ] T021 [US1] 抽取并迁移 [markdown_chunker.py](d:\code\learning_rag\markdown_chunker.py) 逻辑到 `app/services/markdown_ingest_service.py`
- [ ] T022 [US1] 新建 `app/services/blog_source_service.py`，负责把 `Post` 转为内部 `Document`
- [ ] T023 [US1] 新建 `app/services/embedding_service.py`，封装百炼 `text-embedding-v4`
- [ ] T024 [US1] 新建 `app/services/image_understanding_service.py`，封装 OCR 和图片说明生成
- [ ] T025 [US1] 新建 `app/services/ingest_service.py`，串起单篇同步和全量重建流程
- [ ] T026 [US1] 实现 `POST /api/v1/ingest/post` 和 `POST /api/v1/ingest/rebuild` 到 `app/api/routes/ingest.py`
- [ ] T027 [US1] 实现 `GET /api/v1/ingest/jobs/{job_id}` 到 `app/api/routes/ingest.py`

**检查点**：此时应能不依赖聊天接口，独立完成文章索引构建。

---

## Phase 4：用户故事 2 - 博客问答弹窗中的单轮问答（P1）

**目标**：博客前端可以拿到基于文章内容的真实回答、来源和相关图片

**独立验证**：不启用多轮记忆时，`/api/v1/chat` 也能独立完成图文 RAG 回答

### 测试

- [x] T028 [P] [US2] 为 `POST /api/v1/chat` 编写合同测试：`tests/contract/test_chat_api.py`
- [ ] T029 [P] [US2] 为图文召回问答编写集成测试：`tests/integration/test_chat_single_turn.py`
- [ ] T030 [P] [US2] 为来源和图片返回结构编写单元测试：`tests/unit/test_chat_response_format.py`

### 实现

- [ ] T031 [US2] 新建 `app/services/retrieval_service.py`，负责文本与图片文本特征召回
- [ ] T032 [US2] 新建 `app/services/rerank_service.py`，封装百炼 `qwen3-rerank`
- [ ] T033 [US2] 新建 `app/services/answer_service.py`，负责最终回答生成
- [ ] T034 [US2] 将现有检索、重排、父子 chunk 扩展能力迁移并整合到新服务层
- [ ] T035 [US2] 在 `LangGraph` 中实现最小问答图：检索 -> 图片文本召回 -> 重排 -> 上下文裁剪 -> 生成
- [ ] T036 [US2] 实现 `POST /api/v1/chat` 到 `app/api/routes/chat.py`
- [ ] T037 [US2] 实现来源、图片、预算调试信息的响应序列化

**检查点**：此时博客端已可拿到单轮真实回答。

---

## Phase 5：用户故事 3 - 多轮问答与会话记忆（P2）

**目标**：支持按 `session_id` 隔离的多轮上下文与摘要记忆

**独立验证**：同一会话内追问能延续上下文，不同会话不会串话

### 测试

- [ ] T038 [P] [US3] 为会话查询接口编写合同测试：`tests/contract/test_chat_sessions_api.py`
- [ ] T039 [P] [US3] 为多轮追问编写集成测试：`tests/integration/test_chat_multi_turn.py`
- [ ] T040 [P] [US3] 为会话隔离和摘要记忆编写单元测试：`tests/unit/test_session_memory.py`

### 实现

- [ ] T041 [P] [US3] 新建 `app/models/chat_session.py`、`app/models/chat_message.py`、`app/models/memory_record.py`
- [ ] T042 [P] [US3] 新建 `app/repositories/chat_session_repository.py`、`app/repositories/chat_message_repository.py`、`app/repositories/memory_repository.py`
- [ ] T043 [US3] 新建 `app/services/session_service.py`
- [ ] T044 [US3] 新建 `app/services/memory_service.py`
- [ ] T045 [US3] 在 `LangGraph` 运行时接入 checkpoint / persistence，并与业务会话映射
- [ ] T046 [US3] 扩展问答图，加入会话恢复、摘要记忆更新、历史裁剪逻辑
- [ ] T047 [US3] 实现 `GET /api/v1/chat/sessions/{session_id}` 到 `app/api/routes/chat.py`
- [ ] T048 [US3] 实现必要时的 `POST /api/v1/chat/resume` 到 `app/api/routes/chat.py`

**检查点**：此时多轮问答可以独立上线测试。

---

## Phase 6：用户故事 4 - 博客前端开发者接入与 API 契约稳定（P2)

**目标**：让 `geminiBlog` 前端只靠文档就能完成接入

**独立验证**：前端开发者不读后端代码，只看契约和文档也能完成联调

### 测试

- [ ] T049 [P] [US4] 为流式问答接口编写合同测试：`tests/contract/test_chat_stream_api.py`
- [ ] T050 [P] [US4] 为错误结构与限流响应编写合同测试：`tests/contract/test_error_contracts.py`

### 实现

- [ ] T051 [US4] 实现 `POST /api/v1/chat/stream` 到 `app/api/routes/chat.py`
- [ ] T052 [US4] 对齐 [contracts/openapi.yaml](d:\code\learning_rag\specs\001-fastapi-rag-backend\contracts\openapi.yaml) 与实际响应模型
- [ ] T053 [US4] 编写正式 API 文档到 `docs/api/overview.md`、`docs/api/chat.md`、`docs/api/ingest.md`
- [ ] T054 [US4] 编写博客端接入文档到 `docs/integration/geminiblog-chatbot.md`
- [ ] T055 [US4] 在文档中明确 `session_id` 保存策略、来源字段和图片字段使用方式

**检查点**：此时博客端可稳定联调。

---

## Phase 7：用户故事 5 - 维护者部署、排错与二次开发（P2）

**目标**：让后端具备可维护性、可排错性和可扩展性

**独立验证**：新维护者只看文档即可完成本地启动、同步、问答验证和基础排错

### 测试

- [ ] T056 [P] [US5] 为健康检查和配置错误场景编写集成测试：`tests/integration/test_health_and_bootstrap.py`

### 实现

- [x] T057 [US5] 完善 `GET /health` 到 `app/api/routes/health.py`
- [ ] T058 [US5] 编写开发文档到 `docs/backend/architecture.md`、`docs/backend/configuration.md`、`docs/backend/data-flow.md`
- [ ] T059 [US5] 编写排错文档到 `docs/troubleshooting/database.md`、`docs/troubleshooting/api-debugging.md`、`docs/troubleshooting/ocr-and-images.md`
- [ ] T060 [US5] 补齐项目 README 中的后端运行说明
- [ ] T061 [US5] 编写脚本 `scripts/sync_single_post.py`、`scripts/sync_all_posts.py` 作为运维辅助入口
- [ ] T062 [US5] 补充未来对接 Deep Agents 的扩展说明到开发文档，但不在一期引入其运行依赖

**检查点**：此时项目具备交付和后续维护条件。

---

## Phase 8：收尾与跨故事工作

**目标**：清理跨模块问题，补齐一致性和验证

- [ ] T063 [P] 运行并修复全部合同测试、集成测试、单元测试
- [ ] T064 [P] 校验 [quickstart.md](d:\code\learning_rag\specs\001-fastapi-rag-backend\quickstart.md) 中的命令与说明
- [ ] T065 上下文预算调优并记录默认参数
- [ ] T066 统一日志字段、错误码和响应结构
- [ ] T067 清理旧的 CLI demo 入口，只保留迁移期必要文件

## 依赖顺序

### 阶段依赖

- Phase 1 无依赖，可立即开始
- Phase 2 依赖 Phase 1，且阻塞所有用户故事
- Phase 3 完成后，可以先得到“能同步数据”的 MVP
- Phase 4 在 Phase 2 和 Phase 3 后进行，得到单轮问答 MVP
- Phase 5 在 Phase 4 后进行，补齐多轮记忆
- Phase 6 和 Phase 7 可在核心接口稳定后并行推进
- Phase 8 收尾阶段依赖前面目标功能完成

### 用户故事依赖

- US1 是所有后续故事的基础
- US2 依赖 US1
- US3 依赖 US2
- US4 依赖 US2，部分内容可和 US3 并行
- US5 可在 US2 后开始补文档和运维能力，但最终应基于完整实现收尾

## 什么时候可以开始写代码

现在其实就可以开始写代码了。

更准确地说：

- `spec.md`
- `plan.md`
- `research.md`
- `data-model.md`
- `quickstart.md`
- `contracts/openapi.yaml`
- `tasks.md`

这些关键设计文档已经足够支撑进入实现阶段。

如果按风险最小的顺序推进，建议下一步直接开始：

1. Phase 1
2. Phase 2
3. Phase 3

也就是先把 FastAPI 骨架、数据库基础设施和单篇文章同步链路写出来。
