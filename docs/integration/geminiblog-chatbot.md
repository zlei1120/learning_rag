# `geminiBlog` 问答弹窗接入说明

## 目标文件

当前博客侧相关文件：

- `E:\code\geminiBlog\src\components\chat-bot.tsx`
- `E:\code\geminiBlog\src\lib\chat-api.ts`
- `E:\code\geminiBlog\src\app\api\chat\route.ts`
- `E:\code\geminiBlog\src\app\api\chat\stream\route.ts`

## 当前落地状态

当前博客弹窗已经接上普通问答链路：

- 不再使用本地 Mock 问答
- 浏览器请求先走博客自己的 `/api/chat`
- 再由 Next.js route handler 代理到 FastAPI `POST /api/v1/chat`
- `session_id` 已通过 `sessionStorage` 持久化
- AI 消息已支持展示 `sources` 和 `relatedImages`
- 顶部“新对话”按钮会清空本地会话并重新开始

当前已经接入的流式能力：

- 浏览器请求博客自己的 `/api/chat/stream`
- Next.js route handler 代理到 FastAPI `POST /api/v1/chat/stream`
- 前端通过 `fetch + ReadableStream` 消费 SSE 事件
- AI 消息会先显示思考占位，再随着 `message.delta` 增量更新正文
- `message.completed` 会回填最终 `sources`、`relatedImages` 和 `session_id`

当前仍需要记住的一点：

- 这是“后端拆包版伪流式”，不是模型原生 token streaming

## 联调前置条件

在博客端联调聊天弹窗之前，先确认后端基础条件已经满足：

1. `learning_rag` 已执行过数据库迁移
2. 共享的 PostgreSQL 已启用 `pgvector`
3. 文章已经至少完成过一次全量同步

常用命令：

```powershell
uv run alembic upgrade head
uv run python scripts/sync_all_posts.py --scope all
```

如果你共用的是 `E:\code\geminiBlog\docker-compose.yml` 里的数据库，新版 compose 已改为 `pgvector/pgvector:pg16`。

但如果那套数据库是旧 volume 或历史实例，仍然要先在库里补执行：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## 推荐接入顺序

1. 已完成：普通问答 `POST /api/v1/chat`
2. 已完成：来源和图片展示
3. 已完成：流式 `POST /api/v1/chat/stream`
4. 后续可补：更细的会话恢复体验和调试面板

## 一、先改消息结构

当前 `Message` 类型只有文本内容，不够承载真实后端返回。

建议扩成至少下面这些字段：

```ts
type ChatSource = {
  source_type: string;
  label: string;
  slug?: string;
  title_path?: string;
  content_excerpt?: string;
};

type RelatedImage = {
  url: string;
  alt_text?: string;
  caption?: string;
  source_slug?: string;
  title_path?: string;
};

type Message = {
  id: string;
  role: "user" | "ai";
  content: string;
  status?: string;
  sessionId?: string;
  sources?: ChatSource[];
  relatedImages?: RelatedImage[];
};
```

## 二、`session_id` 保存策略

### 推荐做法

- 在 `chat-bot.tsx` 中优先使用 `sessionStorage`
- 建议键名：`gemini-blog-chat-session-id`

### 使用规则

1. 第一次发送问题时，不传 `session_id`
2. 拿到响应里的 `session_id` 后立即写入 `sessionStorage`
3. 同一个弹窗后续追问都带上这个 `session_id`
4. 用户点击“新对话”时，清掉这个值并清空消息列表

### 为什么优先 `sessionStorage`

- 能按标签页隔离匿名访客会话
- 不容易出现多个页面串用同一上下文

## 三、普通模式接入：当前已落地

### 当前实现思路

- 浏览器只请求博客自己的 `/api/chat`
- 博客服务端再代理到 FastAPI，避免浏览器跨域问题
- 聊天组件内部统一通过 `src/lib/chat-api.ts` 发请求

### 推荐抽一个 API 帮助函数

例如在 `E:\code\geminiBlog\src\lib\chat-api.ts` 中增加：

```ts
export type ChatRequest = {
  session_id?: string;
  message: string;
  include_sources?: boolean;
  include_related_images?: boolean;
};

export type ChatResponse = {
  session_id: string;
  answer: string;
  status: string;
  sources: Array<{
    source_type: string;
    label: string;
    slug?: string;
    title_path?: string;
    content_excerpt?: string;
  }>;
  related_images: Array<{
    url: string;
    alt_text?: string;
    caption?: string;
    source_slug?: string;
    title_path?: string;
  }>;
};

export async function requestChat(payload: ChatRequest): Promise<ChatResponse> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message ?? "问答请求失败");
  }

  return response.json();
}
```

### 代理层说明

博客侧普通问答代理文件：

- `E:\code\geminiBlog\src\app\api\chat\route.ts`

它会把请求转发到：

- `${RAG_BACKEND_URL}/api/v1/chat`

如果没有显式配置 `RAG_BACKEND_URL`，当前默认走：

- `http://127.0.0.1:8000`

### `chat-bot.tsx` 中的替换思路

```ts
const sessionKey = "gemini-blog-chat-session-id";

const storedSessionId =
  typeof window !== "undefined" ? window.sessionStorage.getItem(sessionKey) ?? undefined : undefined;

const result = await requestChat({
  session_id: storedSessionId,
  message: input.trim(),
  include_sources: true,
  include_related_images: true,
});

window.sessionStorage.setItem(sessionKey, result.session_id);
```

然后把 AI 回复追加成：

```ts
{
  id: crypto.randomUUID(),
  role: "ai",
  content: result.answer,
  status: result.status,
  sessionId: result.session_id,
  sources: result.sources,
  relatedImages: result.related_images,
}
```

当前实际组件里，还额外补了两点：

1. 如果本地保存的 `session_id` 失效并返回 `404`
   会先清掉旧 `session_id`，再自动重试一次首轮问答

2. 顶部“新对话”按钮会：
   - 清空 `sessionStorage`
   - 重置欢迎消息
   - 重新开始一轮新会话

## 四、流式模式接入：替换打字机体验

### 当前已落地

博客侧流式代理文件：

- `E:\code\geminiBlog\src\app\api\chat\stream\route.ts`

聊天组件当前已经切到流式提交逻辑：

1. 先插入用户消息
2. 预插入一个 `status=streaming` 的 AI 占位消息
3. 请求 `/api/chat/stream`
4. 收到 `message.delta` 后持续更新当前 AI 消息正文
5. 收到 `message.completed` 后回填完整答案、来源和图片
6. 如果本地 `session_id` 失效并返回 `404`，会清掉旧会话并自动重试首轮流式问答

### 关键事实

- `POST /api/v1/chat/stream` 返回的是 `text/event-stream`
- 但它是 `POST`
- 所以不能使用浏览器原生 `EventSource`

必须这样做：

1. 用 `fetch` 发 `POST`
2. 从 `response.body` 读取流
3. 手动解析 SSE 文本中的 `event:` 和 `data:`

## 五、SSE 解析示例

可以在 `chat-api.ts` 中加一个读取函数：

```ts
type StreamEventHandler = (event: string, payload: any) => void;

export async function requestChatStream(
  payload: ChatRequest,
  onEvent: StreamEventHandler,
) {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message ?? "流式问答请求失败");
  }

  if (!response.body) {
    throw new Error("浏览器未返回可读流");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const eventLine = frame.split("\n").find((line) => line.startsWith("event:"));
      const dataLine = frame.split("\n").find((line) => line.startsWith("data:"));
      if (!eventLine || !dataLine) continue;

      const event = eventLine.slice("event:".length).trim();
      const data = JSON.parse(dataLine.slice("data:".length).trim());
      onEvent(event, data);
    }
  }
}
```

## 六、`chat-bot.tsx` 中如何消费这些事件

### `message.delta`

- 用它更新当前 AI 消息的 `content`
- 同时从 payload 中取 `session_id`
- 首次拿到时就写入 `sessionStorage`

### `source`

- 先临时收集到一个数组
- 等 `message.completed` 到来时一起挂到当前 AI 消息上

### `related_image`

- 同样先收集
- 等 `message.completed` 时再写回最终消息对象

### `usage`

- 当前可以先不展示
- 调试模式下可以输出到控制台

### `message.completed`

- 用最终完整 payload 覆盖当前 AI 消息
- 这样即使前面的增量事件有丢失，也能保证最终消息结构完整

## 七、建议的提交逻辑

推荐在 `handleSubmit` 中做下面这几件事：

1. 先插入用户消息
2. 预插入一个 `status=streaming` 的 AI 消息占位
3. 置 `isTyping=true`
4. 发起流式请求
5. 在 `message.delta` 中持续更新 AI 消息文本
6. 在 `message.completed` 后写入 `sources`、`relatedImages`、`sessionId`
7. 结束时置 `isTyping=false`

## 八、来源和图片怎么展示

### 来源展示

每条 AI 消息下方建议加一个“回答依据”区域，展示：

- `label`
- `title_path`
- `content_excerpt`

如果博客已有文章详情页路由，可以用 `slug` 生成跳转。

### 图片展示

每条 AI 消息下方建议加一个“相关图片”区域，展示：

- 缩略图
- `caption`
- `title_path`

### 图片 URL 的当前注意点

- 当前接口返回的是文章原始图片地址
- 如果值是 `/uploads/...`
- 并且你的问答弹窗就在博客前端同域页面里，直接 `<img src={url} />` 即可
- 如果你是在独立调试页面或跨域环境里联调，需要手动拼博客公网域名

## 九、错误处理建议

### 400

- 展示“输入有误，请重新提问”

### 404

- 如果出现在 `/resume` 或会话恢复流程里
- 说明本地保存的 `session_id` 已失效
- 这时应清空本地 `session_id`，重新开始新对话

### 429

- 直接展示后端 `message`
- 如果 `details.retry_after_seconds` 存在，可以提示用户稍后重试

### 500

- 展示统一兜底文案
- 联调期额外打印 `X-Request-ID`

## 十、当前最小可用版本

当前博客弹窗已经至少具备下面这些正式能力：

1. 删除 `MOCK_ANSWERS`
2. 删除 `setTimeout + setInterval` Mock 逻辑
3. 接普通问答 `POST /api/v1/chat`
4. 接流式问答 `POST /api/v1/chat/stream`
5. 把 `session_id` 存入 `sessionStorage`
6. 在 AI 消息下方展示 `sources` 和 `relatedImages`
