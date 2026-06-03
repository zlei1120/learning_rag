# 数据模型设计：FastAPI RAG 后端

## 设计目标

本文件用于明确一期实现中的核心数据结构，重点解决以下问题：

- 博客知识库如何建模
- 图片 OCR / caption 如何入库
- 多轮会话如何隔离
- 摘要记忆如何持久化
- `LangGraph` 运行状态如何与业务会话状态分层
- 所有人不会共用同一套对话记忆

## 设计原则

### 1. 文章知识库全站共享

共享范围仅限：

- 已发布文章
- chunk
- 向量
- 图片 OCR
- 图片说明

这部分是博客公共知识库，所有访客共享。

### 2. 会话历史严格隔离

隔离范围包括：

- 会话线程
- 消息历史
- 摘要记忆
- 未来可能的长期记忆

这部分必须至少按 `session_id` 隔离。

### 3. `LangGraph` 运行状态不等于业务会话状态

需要明确区分：

- 业务会话：用户眼中的一段连续问答
- 图运行状态：`LangGraph` 在某次请求中用于中断/恢复的内部状态

业务会话必须稳定、可读、可查；图运行状态可以更技术化。

### 4. 上下文预算是配置对象，不是临时实现细节

上下文预算虽然不一定单独成表，但必须以显式结构存在，便于：

- 调优
- 记录
- 解释为什么某些内容没进入最终 prompt

## 外部真源数据

### `geminiBlog.Post`

来源路径：

- `E:\code\geminiBlog\prisma\schema.prisma`

关键字段：

- `id`
- `title`
- `slug`
- `content`
- `excerpt`
- `category`
- `tags`
- `published`
- `date`
- `series`
- `seriesOrder`
- `createdAt`
- `updatedAt`

用途：

- 作为 RAG 索引的正式文章真源
- 不直接在本仓库修改，只读取和同步

## RAG 侧核心数据模型

### 1. `rag_documents`

作用：

- 表示一篇文章在 RAG 侧的主索引记录

建议字段：

- `id`
- `source_post_id`
- `slug`
- `title`
- `published`
- `source_updated_at`
- `content_hash`
- `excerpt`
- `category`
- `tags_json`
- `series`
- `series_order`
- `last_synced_at`
- `sync_status`
- `created_at`
- `updated_at`

关键约束：

- `source_post_id` 唯一
- `slug` 建唯一索引

说明：

- 这里不直接保存全部正文作为主内容源，正文以 chunk 为主组织
- 但可以保留必要的摘要字段方便排错与后台查询

### 2. `rag_chunks`

作用：

- 保存文章切分后的文本块

建议字段：

- `id`
- `document_id`
- `section_id`
- `title_path`
- `section_title`
- `heading_level`
- `section_index`
- `chunk_index`
- `child_chunk_index`
- `content`
- `content_hash`
- `token_estimate`
- `has_images`
- `created_at`
- `updated_at`

关键索引：

- `(document_id, chunk_index)`
- `section_id`
- `content_hash`

说明：

- `title_path` 必须保留，因为它对教程类博客非常关键
- `token_estimate` 用于上下文预算控制

### 3. `rag_embeddings`

作用：

- 保存每个文本 chunk 的向量化结果

建议字段：

- `id`
- `chunk_id`
- `embedding_model`
- `embedding_dim`
- `embedding_version`
- `embedding_vector`
- `created_at`
- `updated_at`

关键索引：

- `chunk_id`
- `embedding_model + embedding_version`
- `embedding_vector` 上建立 `pgvector` 索引

说明：

- 一期建议按“一个 chunk 一条主向量记录”落地
- 后续如果换模型，可通过 `embedding_version` 演进

### 4. `rag_images`

作用：

- 保存文章中的图片引用和图片所在上下文

建议字段：

- `id`
- `document_id`
- `source_url`
- `normalized_url`
- `alt_text`
- `markdown_ref`
- `title_path`
- `section_id`
- `image_index`
- `neighbor_text_before`
- `neighbor_text_after`
- `image_hash`
- `created_at`
- `updated_at`

说明：

- `normalized_url` 用于稳定去重
- `neighbor_text_before/after` 用于提高图文关联可解释性

### 5. `rag_image_features`

作用：

- 保存图片 OCR、caption、摘要等文本特征

建议字段：

- `id`
- `image_id`
- `ocr_text`
- `ocr_text_summary`
- `caption_text`
- `feature_summary`
- `ocr_model`
- `caption_model`
- `feature_hash`
- `status`
- `error_message`
- `token_estimate`
- `created_at`
- `updated_at`

说明：

- 不建议只存 `ocr_text`，还要保留可压缩后的摘要字段
- `token_estimate` 用于单独控制图片文本进入上下文的预算

### 6. `rag_chunk_images`

作用：

- 建立 chunk 和图片之间的多对多关系

建议字段：

- `id`
- `chunk_id`
- `image_id`
- `relation_type`
- `distance_score`
- `created_at`

说明：

- `relation_type` 可取：
  - `same_section`
  - `adjacent_reference`
  - `explicit_markdown_reference`

## 同步与任务模型

### 7. `rag_ingest_jobs`

作用：

- 跟踪同步任务

建议字段：

- `id`
- `job_type`
- `target_post_id`
- `target_slug`
- `status`
- `trigger_source`
- `started_at`
- `finished_at`
- `retry_count`
- `error_message`
- `payload_json`
- `created_at`
- `updated_at`

说明：

- `job_type` 可取：
  - `single_post_sync`
  - `full_rebuild`
  - `embedding_rebuild`
  - `image_feature_rebuild`

## 会话与记忆模型

### 8. `chat_sessions`

作用：

- 表示一段多轮问答线程

建议字段：

- `id`
- `session_id`
- `user_key`
- `session_scope`
- `status`
- `summary_text`
- `last_message_at`
- `last_checkpoint_ref`
- `created_at`
- `updated_at`

关键约束：

- `session_id` 唯一

说明：

- 匿名访客至少依赖 `session_id`
- 如果未来有登录态，再引入 `user_key`
- `summary_text` 是本会话的短摘要，不是长期记忆

### 9. `chat_messages`

作用：

- 存每轮消息

建议字段：

- `id`
- `session_id`
- `message_index`
- `role`
- `content`
- `content_summary`
- `source_payload_json`
- `budget_included`
- `trimmed`
- `token_estimate`
- `created_at`

说明：

- `budget_included` 表示这条消息是否进入过当前轮最终上下文
- `trimmed` 表示是否已从“最近消息窗口”中裁出

### 10. `memory_records`

作用：

- 保存短期摘要记忆和预留长期记忆

建议字段：

- `id`
- `session_id`
- `user_key`
- `memory_scope`
- `memory_type`
- `content`
- `content_hash`
- `importance_score`
- `expires_at`
- `created_at`
- `updated_at`

建议取值：

- `memory_scope`
  - `session`
  - `user`
- `memory_type`
  - `summary`
  - `preference`
  - `fact`
  - `task`

一期约束：

- 一期以 `session` + `summary` 为主
- `user` 作用域先只预留

## LangGraph 持久化状态

### 11. `langgraph_checkpoints` 或等价存储

作用：

- 保存图运行时状态与恢复点

设计原则：

- 可以采用 `LangGraph` 官方支持的持久化方案
- 这部分不应直接替代 `chat_sessions`
- 业务会话语义仍由我们的业务表维护

建议：

- 将图状态与业务数据分开
- `chat_sessions.last_checkpoint_ref` 只保存引用

## 上下文预算模型

### 12. `context_budget_policy`（配置对象，首期不强制单独建表）

作用：

- 约束每轮真正进入模型的上下文大小

建议字段：

- `max_input_tokens`
- `system_prompt_tokens`
- `recent_messages_tokens`
- `summary_memory_tokens`
- `retrieved_chunks_tokens`
- `image_feature_tokens`
- `reserved_output_tokens`

建议首期实现方式：

- 先从配置文件或环境变量驱动
- 需要时写入请求日志，便于调优

## 作用域隔离规则

### 共享数据

- `rag_documents`
- `rag_chunks`
- `rag_embeddings`
- `rag_images`
- `rag_image_features`

### 会话隔离数据

- `chat_sessions`
- `chat_messages`
- `memory_records` 中 `memory_scope=session` 的记录

### 未来用户隔离数据

- `memory_records` 中 `memory_scope=user` 的记录

## 绝对禁止的错误设计

- 把所有访客的消息放在同一个“全局历史”里
- 让没有作用域的记忆记录参与所有用户问答
- 让 `LangGraph` 进程内内存成为唯一会话来源
- 把 OCR 原文不加预算控制地直接拼进 prompt
- 把知识库和记忆库混成同一类记录

## 关系概览

```text
Post (geminiBlog)
  └── rag_documents
        ├── rag_chunks
        │     ├── rag_embeddings
        │     └── rag_chunk_images
        └── rag_images
              └── rag_image_features

chat_sessions
  ├── chat_messages
  └── memory_records

chat_sessions
  └── langgraph_checkpoints (引用关系，不要求同表实现)
```

## 一期实现建议

优先实现：

- `rag_documents`
- `rag_chunks`
- `rag_embeddings`
- `rag_images`
- `rag_image_features`
- `rag_ingest_jobs`
- `chat_sessions`
- `chat_messages`
- `memory_records`

可以延后优化：

- 用户级长期记忆
- 多套 embedding 并存
- 更复杂的记忆评分体系
- 细粒度图片向量
