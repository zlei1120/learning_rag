# 同步接口

## 作用

同步接口负责把 `geminiBlog` 的文章真源写入当前 RAG 存储，包括：

- 文章正文分块
- 文本 embedding
- 图片抽取
- 图片 OCR / caption
- 图文关联关系

## 1. `POST /api/v1/ingest/post`

### 用途

- 同步单篇文章
- 适合博客后台保存某篇文章后，只更新这一篇

### 请求体

```json
{
  "post_id": null,
  "slug": "hello-nextjs",
  "force_rebuild": false
}
```

### 字段说明

- `post_id`
  博客数据库中的文章主键

- `slug`
  博客文章 slug

- `force_rebuild`
  预留给后续“即使内容哈希未变也强制重建”的扩展参数

### 当前实现说明

- 当前后端会在请求内直接执行同步逻辑
- 因此虽然接口状态码是 `202`
- 但响应体里的 `status` 很可能已经是最终状态，而不是异步队列里的中间状态

### 响应示例

```json
{
  "job_id": "job-single-001",
  "job_type": "single_post_sync",
  "status": "succeeded",
  "target_slug": "hello-nextjs",
  "started_at": "2026-06-04T08:00:00Z",
  "finished_at": "2026-06-04T08:00:12Z",
  "error_message": null
}
```

## 2. `POST /api/v1/ingest/rebuild`

### 用途

- 触发全量或范围重建

### 请求体

```json
{
  "scope": "all",
  "force": false
}
```

### `scope` 取值

- `all`
  全量重建文本和图片索引

- `embeddings_only`
  预留给后续只重建文本向量

- `image_features_only`
  预留给后续只重建图片特征

### 当前实现说明

- 当前三个 `scope` 都会统一走完整同步主流程
- 也就是它们现在更多是“对外契约先稳定”，不是完全分开的执行通路

## 3. `GET /api/v1/ingest/jobs/{job_id}`

### 用途

- 查询某次同步任务状态

### 响应示例

```json
{
  "job_id": "job-single-001",
  "job_type": "single_post_sync",
  "status": "succeeded",
  "target_slug": "hello-nextjs",
  "started_at": "2026-06-04T08:00:00Z",
  "finished_at": "2026-06-04T08:00:12Z",
  "error_message": null
}
```

## 同步成功后会发生什么

单篇同步成功后，当前后端会完成以下步骤：

1. 从博客 PostgreSQL 真源读取文章
2. 解析 Markdown 标题结构
3. 按窗口切分文本 chunk
4. 提取图片、图片前后文和标题路径
5. 生成文本向量
6. 生成图片 OCR / caption / feature summary
7. 重建图文关联
8. 更新 RAG 文档同步状态

## 常见错误

### 404 `post_not_found`

适用于：

- `post_id` 或 `slug` 找不到文章
- 文章未发布，无法进入对外知识库

### 404 `not_found`

适用于：

- 查询不存在的 `job_id`

### 400 `invalid_request`

适用于：

- `post_id` 和 `slug` 同时为空
- `scope` 不是允许值

## 联调建议

- 后台保存单篇文章后，优先调用 `POST /api/v1/ingest/post`
- 首次建库或模型调整后，再调用 `POST /api/v1/ingest/rebuild`
- 如果要做更真实的后台异步任务体验，后续可以把当前同步实现抽成真正的队列任务
