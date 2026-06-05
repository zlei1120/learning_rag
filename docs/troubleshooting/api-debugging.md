# API 联调与排错

## 一、先分清是哪一类问题

当前 API 问题大多落在以下几类：

1. 请求体不合法
2. `session_id` 使用错误
3. 流式接口接法不对
4. 限流或内部异常
5. 会话恢复逻辑理解不一致

## 二、统一先看这三样

1. HTTP 状态码
2. 响应体里的 `error_code` / `message`
3. 响应头里的 `X-Request-ID`

如果需要后端继续排日志，`X-Request-ID` 是最有价值的线索。

## 三、常见错误码

### 400 `invalid_request`

常见原因：

- `message` 为空
- `session_id` 格式非法
- 请求体多传了未定义字段

当前合法的 `session_id` 规则：

- 8 到 64 位
- 只允许字母、数字、下划线和中划线
- 不能带空格

### 404 `not_found`

常见原因：

- 查询了不存在的会话
- 调 `/resume` 时会话不存在
- 查询了不存在的同步任务

### 429 `rate_limited`

前端处理建议：

- 直接展示后端 `message`
- 如果有 `details.retry_after_seconds`，按这个时间提示稍后重试

### 503 `database_unavailable`

常见原因：

- PostgreSQL 服务不可达
- SSH 隧道没有建立，或本地端口写错
- `DATABASE_URL` 的用户名、密码、库名和实际数据库不一致

建议动作：

1. 先调 `GET /health`，确认 `database` 是否为 `unavailable`
2. 本地隧道场景确认 `.env` 里的端口是本地监听端口，例如 `5433`
3. 修改 `.env` 后重启后端服务
4. 如果端口可达但仍失败，重点检查远端数据库密码和用户权限

### 500 `internal_error`

建议动作：

1. 记录 `X-Request-ID`
2. 查看后端日志
3. 结合请求体复现

## 四、流式接口的常见坑

### 坑 1：把 `POST /api/v1/chat/stream` 当成 `EventSource`

这是最容易踩的坑。

原因：

- 浏览器原生 `EventSource` 只适合 GET
- 当前流式接口是 POST

正确方式：

- 用 `fetch`
- 读取 `response.body`
- 自己解析 SSE 文本

### 坑 2：以为它是模型原生流式

当前实现不是原生 token streaming，而是：

1. 后端先拿完整回答
2. 再拆成多个 `message.delta`

所以如果你在前端观测到“首字还是要等一下”，这是当前实现预期，不一定是 bug。

### 坑 3：只消费 `message.delta`，没消费 `message.completed`

建议前端一定处理最终完成事件，因为：

- `message.completed` 会带完整结构
- 包括 `sources` 和 `related_images`

## 五、`session_id` 使用错误

### 正确策略

- 首轮不传
- 后端返回后保存
- 后续同一会话持续复用

### 常见错误

- 多个浏览器标签页共用一个固定 `session_id`
- 把另一个用户或另一篇文章上下文误复用到新对话
- 页面刷新后保留了旧 `session_id`，但后台会话已经不存在

### 推荐修复

- 匿名博客场景优先用 `sessionStorage`
- 页面新开会话时清空本地保存的 `session_id`

## 六、`/chat` 和 `/resume` 的区别

### `/api/v1/chat`

- 可用于首轮提问
- 也可用于带已有 `session_id` 的后续追问

### `/api/v1/chat/resume`

- 只适用于“这个会话必须已经存在”的场景
- 如果不存在，会直接返回 `404`

当前阶段如果你只是普通连续聊天，直接复用 `POST /api/v1/chat` 就够了。

## 七、快速定位思路

### 问题：接口直接报 400

先看：

- 请求体 JSON 是否合法
- 字段名是否和契约一致
- `message` 是否为空
- `session_id` 是否带了空格或中文

### 问题：会话恢复失败

先看：

- 本地保存的 `session_id` 是否还是旧值
- `GET /api/v1/chat/sessions/{session_id}` 是否能查到

### 问题：流式 UI 没有输出

先看：

- 是否误用了 `EventSource`
- 是否正确读取了 `response.body`
- 是否按 `\n\n` 切分 SSE 帧
- 是否同时处理了 `message.completed`
