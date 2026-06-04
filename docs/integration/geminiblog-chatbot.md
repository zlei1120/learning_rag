# `geminiBlog` 问答弹窗接入说明

## 目标文件

当前前端替换入口：

- `E:\code\geminiBlog\src\components\chat-bot.tsx`

这个组件现在还是纯 Mock：

- 本地 `messages`
- `setTimeout` 模拟请求
- `setInterval` 模拟打字机输出

建议先保留现有 UI，只替换数据层和流式处理逻辑。

## 推荐接入顺序

1. 先把 Mock 请求改成 `POST /api/v1/chat`
2. 跑通真实问答、来源和图片展示
3. 再把提交逻辑升级成 `POST /api/v1/chat/stream`
4. 最后补 `session_id` 持久化和会话恢复

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

## 三、普通模式接入：先替换当前 Mock

### 最小替换点

当前 `handleSubmit` 里这段逻辑：

- `setTimeout(...)`
- 随机取 `MOCK_ANSWERS`
- `setInterval(...)` 逐字输出

可以先整体替换为一次真实 `fetch`。

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
  const response = await fetch("http://127.0.0.1:8000/api/v1/chat", {
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

## 四、流式模式接入：替换打字机体验

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
  const response = await fetch("http://127.0.0.1:8000/api/v1/chat/stream", {
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
2. 预插入一个空的 AI 消息占位
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

## 十、推荐的最小落地版本

如果你想先最快接通 `chat-bot.tsx`，建议按这个最小范围改：

1. 删除 `MOCK_ANSWERS`
2. 删除 `setTimeout + setInterval` Mock 逻辑
3. 接 `POST /api/v1/chat`
4. 把 `session_id` 存入 `sessionStorage`
5. 在 AI 消息下方把 `sources` 和 `relatedImages` 展示出来

等这个稳定后，再升级到 `/api/v1/chat/stream`。
