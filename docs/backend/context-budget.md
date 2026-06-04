# 上下文预算默认值

## 目的

本文档专门记录当前问答链路的默认上下文预算参数、分配逻辑和调优建议。

对应实现：

- `app/core/config.py`
- `app/services/context_budget_service.py`

## 一、当前默认值

### 总预算

- `CHAT_CONTEXT_MAX_TOKENS=24000`

### 分项预算

- `CHAT_CONTEXT_RECENT_MESSAGES_TOKENS=3000`
- `CHAT_CONTEXT_SUMMARY_TOKENS=2000`
- `CHAT_CONTEXT_RETRIEVAL_TOKENS=12000`
- `CHAT_CONTEXT_IMAGE_TOKENS=4000`
- `CHAT_CONTEXT_RESERVED_OUTPUT_TOKENS=3000`

### 相关联的辅助参数

- `CHAT_HISTORY_MESSAGE_LIMIT=8`
- `CHAT_SUMMARY_MAX_CHARS=600`
- `CHAT_RETRIEVAL_TOP_K=8`
- `CHAT_IMAGE_TOP_K=3`
- `CHAT_PARENT_CHUNK_WINDOW_SIZE=2`

## 二、这些默认值为什么这样分

当前知识库的主要特点是：

- 文章规模还不算特别大
- 教程类内容较多
- 图片里的界面信息对理解步骤很重要
- 需要兼顾多轮追问，而不是只做单轮回答

所以当前默认分配遵循下面的思路：

### 1. 检索正文占大头

- `12000` token 留给正文 chunk

原因：

- 教程和原理说明主要仍来自正文
- 如果正文预算太小，回答会变得碎片化

### 2. 图片文本单独保留一块

- `4000` token 留给图片 OCR / caption

原因：

- 教程截图中的端口、按钮、配置项往往是关键语义
- 但图片文本又不能无限放大，否则会挤占正文

### 3. 最近消息优先于更长历史

- `3000` token 给最近消息
- `2000` token 给摘要记忆

原因：

- 多轮追问里，最近几轮通常最关键
- 更早历史更适合压缩成摘要，而不是全文回放

### 4. 必须固定预留输出空间

- `3000` token 保留给模型输出

原因：

- 否则输入塞满后，模型容易没有足够空间完成回答

## 三、分项预算和总预算的关系

当前默认值满足：

```text
3000 + 2000 + 12000 + 4000 + 3000 = 24000
```

也就是：

- 最近消息
- 摘要记忆
- 检索正文
- 图片文本
- 输出预留

五部分刚好拼成当前的总预算。

## 四、当前实现里的真实裁剪方式

### 最近消息

- 先按 `CHAT_HISTORY_MESSAGE_LIMIT` 控制条数
- 再按 `CHAT_CONTEXT_RECENT_MESSAGES_TOKENS` 控制预算

### 摘要记忆

- 当前会把较早历史压缩成一段文本
- 长度上限由 `CHAT_SUMMARY_MAX_CHARS` 控制

### 正文 chunk

- 召回后会先重排
- 再做父子 chunk 扩展
- 最后按 `CHAT_CONTEXT_RETRIEVAL_TOKENS` 裁剪

### 图片特征

- 当前会按 `CHAT_IMAGE_TOP_K` 先限制图片候选数
- 再按 `CHAT_CONTEXT_IMAGE_TOKENS` 裁剪

## 五、什么时候应该调这些参数

### 现象 1：多轮追问经常忘记上文

优先调整：

- `CHAT_CONTEXT_RECENT_MESSAGES_TOKENS`
- `CHAT_HISTORY_MESSAGE_LIMIT`
- `CHAT_SUMMARY_MAX_CHARS`

### 现象 2：回答能抓到文章主题，但步骤细节不足

优先调整：

- `CHAT_CONTEXT_RETRIEVAL_TOKENS`
- `CHAT_RETRIEVAL_TOP_K`
- `CHAT_PARENT_CHUNK_WINDOW_SIZE`

### 现象 3：截图相关问题答不上来

优先调整：

- `CHAT_CONTEXT_IMAGE_TOKENS`
- `CHAT_IMAGE_TOP_K`
- `BLOG_PUBLIC_BASE_URL`

### 现象 4：延迟或成本明显升高

优先检查：

- `CHAT_RETRIEVAL_TOP_K`
- `CHAT_IMAGE_TOP_K`
- `CHAT_CONTEXT_RETRIEVAL_TOKENS`
- `CHAT_CONTEXT_IMAGE_TOKENS`

## 六、当前建议的调优顺序

建议不要一次同时改很多参数，优先按下面顺序调：

1. `CHAT_RETRIEVAL_TOP_K`
2. `CHAT_CONTEXT_RETRIEVAL_TOKENS`
3. `CHAT_IMAGE_TOP_K`
4. `CHAT_CONTEXT_IMAGE_TOKENS`
5. `CHAT_CONTEXT_RECENT_MESSAGES_TOKENS`
6. `CHAT_HISTORY_MESSAGE_LIMIT`

原因是：

- 先调候选规模，能最快看到性能和效果变化
- 再调 token 预算，能更细地控制上下文占比

## 七、当前默认值的适用边界

这套默认值适合当前这一阶段：

- 博客文章数量不算极大
- 教程类和图文类问题都要兼顾
- 主目标是先把博客问答弹窗接稳

如果后续出现下面变化，就应该重新评估：

- 文章数量显著增长
- 图像类内容占比明显上升
- 模型上下文窗口或计费模型发生变化
- 后续接入更复杂的 Agent 编排

## 八、调优时如何观测

建议至少同时观察三类结果：

1. 回答质量
   看是否还能答到关键步骤、参数和截图信息

2. 多轮连续性
   看追问时是否还记得前文

3. 延迟与成本
   看回答等待时间和模型 token 消耗是否失控

如果要前端联调时快速观察预算，可在请求中开启：

- `debug_context=true`

这时接口响应会带回 `context_budget` 字段。
