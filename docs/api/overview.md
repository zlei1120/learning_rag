# API 总览

## 适用范围

本文档对应当前仓库：

- `D:\code\learning_rag`

主要服务对象：

- `E:\code\geminiBlog` 的博客问答弹窗接入
- 后端维护者联调与排错

正式契约文件位于：

- `specs/001-fastapi-rag-backend/contracts/openapi.yaml`

更细的接口说明请继续查看：

- `docs/api/chat.md`
- `docs/api/ingest.md`
- `docs/integration/geminiblog-chatbot.md`

## 基础信息

- 默认本地地址：`http://127.0.0.1:8000`
- 健康检查：`GET /health`
- 聊天接口前缀：`/api/v1/chat`
- 同步接口前缀：`/api/v1/ingest`

## 响应约定

### 1. 会话隔离

- 所有多轮上下文都按 `session_id` 隔离
- 不同 `session_id` 不共享历史消息、摘要记忆或最近检查点
- 前端第一次提问时可以不传 `session_id`，后端会自动生成并在响应中返回
- 前端拿到 `session_id` 后，后续同一轮对话必须持续复用它

### 2. 统一错误结构

所有业务错误统一返回：

```json
{
  "error_code": "invalid_request",
  "message": "请求参数校验失败。",
  "details": {
    "errors": [
      {
        "field": "message",
        "message": "String should have at least 1 character",
        "error_type": "string_too_short"
      }
    ]
  }
}
```

常见错误码：

- `invalid_request`：请求参数不合法，通常是 `400`
- `not_found`：资源不存在，通常是 `404`
- `rate_limited`：限流，通常是 `429`
- `database_unavailable`：数据库暂时不可用，通常是 `503`
- `internal_error`：未处理异常，通常是 `500`

### 3. 请求链路标识

- 服务会在响应头返回 `X-Request-ID`
- 前后端联调排错时，建议把这个值带进日志

## 聊天接口选择建议

- `POST /api/v1/chat`
  适合先快速接通功能，后端一次性返回完整回答

- `POST /api/v1/chat/stream`
  适合需要“边显示边打字”的问答弹窗

- `POST /api/v1/chat/resume`
  适合“必须基于一个已存在会话继续追问”的场景

- `GET /api/v1/chat/sessions/{session_id}`
  适合页面刷新后恢复会话摘要、校验会话是否存在

## 当前实现的重要限制

- `POST /api/v1/chat/stream` 当前是“伪流式”
- 后端会先完整拿到回答，再拆成多个 `message.delta` 事件输出
- 这意味着前端可以先完成流式 UI 联调，但首字返回时间不会像模型原生流式那样真正提前

- `POST /api/v1/ingest/post` 和 `POST /api/v1/ingest/rebuild` 当前虽然返回 `202`
- 但后端实现仍然在请求内执行完整同步流程
- 因此当前返回体中的 `status` 很可能已经是 `succeeded` 或 `failed`，而不一定停留在 `queued`

## 问答返回中的关键字段

### `sources`

- 用于给前端展示“答案依据来自哪些文章片段”
- 当前每项主要包含：
  - `label`：来源标题
  - `slug`：文章 slug
  - `title_path`：章节路径
  - `content_excerpt`：裁剪后的正文摘录

### `related_images`

- 用于给前端展示和答案最相关的教程截图或配图
- 当前每项主要包含：
  - `url`：文章中原始图片地址
  - `alt_text`：Markdown 图片 alt
  - `caption`：OCR / caption 或回退说明
  - `source_slug`：图片所属文章 slug
  - `title_path`：图片所在章节路径

## 推荐的前端落地顺序

1. 先接 `POST /api/v1/chat`，把真实回答、来源和图片显示出来
2. 再把提交逻辑切到 `POST /api/v1/chat/stream`
3. 最后补 `session_id` 持久化、页面刷新恢复和错误提示
