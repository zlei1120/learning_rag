# 聊天接口

## 适用前端

当前文档主要服务于：

- `E:\code\geminiBlog\src\components\chat-bot.tsx`

如果博客弹窗先求稳，建议先接普通接口；如果要保留现在的打字机体验，再接流式接口。

## 1. `POST /api/v1/chat`

### 用途

- 发起一轮普通问答
- 支持首轮提问，也支持带 `session_id` 的后续追问
- 一次性返回完整答案、来源和相关图片

### 请求体

```json
{
  "session_id": "sess_demo_001",
  "message": "数据库配置那篇教程里，5432 端口是什么意思？",
  "user_key": null,
  "include_sources": true,
  "include_related_images": true,
  "debug_context": false
}
```

### 字段说明

- `session_id`
  首轮可以不传；后端会生成一个新的 `sess_...` 并返回

- `message`
  当前轮问题，不能为空

- `user_key`
  预留的用户标识。匿名博客场景可以不传

- `include_sources`
  是否返回 `sources`

- `include_related_images`
  是否返回 `related_images`

- `debug_context`
  是否返回上下文预算信息。生产 UI 默认建议关闭，调试时再打开

### 响应示例

```json
{
  "session_id": "sess_1234567890abcdef1234567890abcdef",
  "answer": "这里的端口指 PostgreSQL 对外监听的 5432 端口。",
  "status": "completed",
  "sources": [
    {
      "source_type": "post_chunk",
      "label": "数据库教程",
      "slug": "db-guide",
      "title_path": "数据库教程 > 准备数据库",
      "content_excerpt": "先确认 PostgreSQL 服务已经启动，再检查 5432 端口。"
    }
  ],
  "related_images": [
    {
      "url": "/uploads/tutorial/db-step.png",
      "alt_text": "数据库配置截图",
      "caption": "截图展示了端口和账号权限。",
      "source_slug": "db-guide",
      "title_path": "数据库教程 > 准备数据库"
    }
  ],
  "usage": {
    "prompt_tokens": 120,
    "completion_tokens": 32,
    "total_tokens": 152
  }
}
```

### `status` 字段说明

- 当前已落地返回值主要是 `completed`
- `resume_required` 和 `refused` 目前是后续扩展保留值
- 前端当前可以把非 `completed` 统一当作“需要特殊处理的异常状态”

## 2. `POST /api/v1/chat/stream`

### 用途

- 发起流式问答
- 适合问答弹窗里的“边生成边显示”体验

### 当前实现方式

- 当前实现不是模型原生 token streaming
- 后端会先调用一次完整问答
- 然后把完整答案拆成多个 `message.delta` 事件输出
- 所以它更像“后端拆包版打字机流”

这点要明确告诉前端，避免误以为首字时间会显著提前。

### 请求体

请求体和 `POST /api/v1/chat` 完全一致。

### 返回类型

- `Content-Type: text/event-stream`

### 事件顺序

当前实现中，事件大致按以下顺序出现：

1. `message.delta`
2. `source`
3. `related_image`
4. `context_budget`
5. `usage`
6. `message.completed`

### 事件示例

```text
event: message.delta
data: {"session_id":"sess_1234567890abcdef1234567890abcdef","delta":"这里的端口","accumulated":"这里的端口"}

event: source
data: {"source_type":"post_chunk","label":"数据库教程","slug":"db-guide","title_path":"数据库教程 > 准备数据库","content_excerpt":"先确认 PostgreSQL 服务已经启动，再检查 5432 端口。"}

event: related_image
data: {"url":"/uploads/tutorial/db-step.png","alt_text":"数据库配置截图","caption":"截图展示了端口和账号权限。","source_slug":"db-guide","title_path":"数据库教程 > 准备数据库"}

event: usage
data: {"prompt_tokens":120,"completion_tokens":32,"total_tokens":152}

event: message.completed
data: {"session_id":"sess_1234567890abcdef1234567890abcdef","answer":"这里的端口指 PostgreSQL 对外监听的 5432 端口。","status":"completed","sources":[...],"related_images":[...]}
```

### 浏览器端接法

- 这是 `POST` 请求，不能直接用 `EventSource`
- 浏览器里应使用 `fetch` 获取 `ReadableStream`
- 然后按 SSE 文本格式自己解析 `event:` 和 `data:`

这个点对于 `geminiBlog` 接入非常关键。

## 3. `POST /api/v1/chat/resume`

### 用途

- 只允许在一个已存在的会话上继续追问

### 请求体

```json
{
  "session_id": "sess_existing_001",
  "message": "继续说一下这张截图里的端口配置。"
}
```

### 当前语义

- 当前实现里，`/resume` 本质上等于：
  - 先校验这个 `session_id` 对应的会话是否存在
  - 再基于该会话继续调用问答主流程

- 它当前还没有真正消费 `resume_token`
- `resume_token` 仍是后续扩展保留字段

### 什么时候用 `/resume`

- 页面已经保存了 `session_id`
- 并且你希望这次调用“如果会话不存在就立即报错”

如果只是常规连续聊天，其实直接调用 `POST /api/v1/chat` 并传回同一个 `session_id` 也可以。

## 4. `GET /api/v1/chat/sessions/{session_id}`

### 用途

- 查询会话是否存在
- 读取会话摘要、状态和最近更新时间
- 页面刷新后做会话恢复前检查

### 响应示例

```json
{
  "session_id": "sess_demo_001",
  "status": "active",
  "summary": "用户先问了数据库配置，再追问了 5432 端口的含义。",
  "created_at": "2026-06-04T08:00:00Z",
  "updated_at": "2026-06-04T08:05:00Z",
  "last_message_at": "2026-06-04T08:05:00Z"
}
```

### `status` 字段说明

- 当前实现主要返回 `active`
- `archived`、`expired` 目前属于后续扩展保留值

## `session_id` 保存策略

### 推荐方案

- 匿名博客弹窗优先存到 `sessionStorage`
- 建议 key 例如：`gemini-blog-chat-session-id`
- 用户在当前标签页连续追问时复用同一个值
- 用户点击“开始新对话”时主动删除这个值

### 为什么优先 `sessionStorage`

- 可以天然按标签页隔离
- 能减少多个页面串用同一会话的风险
- 更符合匿名访客的临时聊天体验

### 什么时候用 `localStorage`

- 希望用户刷新页面或重新打开标签后继续上次聊天
- 并且能接受“同浏览器多页面可能复用同一会话”的行为

## `sources` 和 `related_images` 的展示建议

### `sources`

- 推荐展示为“回答依据”区域
- 至少展示 `label`、`title_path`、`content_excerpt`
- `slug` 可用来跳转到对应文章详情页

### `related_images`

- 推荐作为答案下方的“相关截图”区域
- `caption` 优先作为图片说明
- `title_path` 可作为“这张图来自文章哪个章节”的补充说明

### 图片 URL 的当前约束

- 当前后端返回的是文章中原始图片地址
- 如果文章里写的是 `/uploads/...` 相对路径，接口返回也会是相对路径
- 如果问答弹窗运行在博客同域页面里，前端可以直接渲染
- 如果你在独立调试页联调，需要手动给它补上博客公网域名

## 错误处理

### 400 `invalid_request`

适用于：

- `message` 为空
- `session_id` 格式不合法
- 请求体字段拼错或多传

### 404 `not_found`

适用于：

- `session_id` 对应会话不存在
- 恢复会话时找不到目标会话

### 429 `rate_limited`

响应示例：

```json
{
  "error_code": "rate_limited",
  "message": "请求过于频繁，请稍后再试。",
  "details": {
    "retry_after_seconds": 10,
    "scope": "chat"
  }
}
```

前端建议：

- 直接展示 `message`
- 如果有 `retry_after_seconds`，可以给出倒计时或“稍后重试”的提示

### 500 `internal_error`

- 统一展示“服务暂时不可用，请稍后再试”
- 联调时同时记录 `X-Request-ID`
