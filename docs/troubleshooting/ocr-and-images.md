# OCR 与图片排错

## 一、先理解当前图片链路

当前图片相关能力不是直接做“图片向量搜图”，而是先做图片文本化：

1. 解析 Markdown 图片
2. 下载图片
3. 做 OCR
4. 做 caption
5. 生成 `feature_summary`
6. 把图片文本特征纳入问答召回

所以大多数图片问题，本质上是：

- 图片地址问题
- OCR / caption 调用问题
- 图片文本没有进入最终上下文

## 二、最常见问题 1：图片地址不可访问

当前后端会优先把图片地址转成绝对地址。

如果文章里是相对路径：

- `/uploads/tutorial/a.png`

就必须配置：

- `BLOG_PUBLIC_BASE_URL`

否则无法下载图片。

### 诊断方法

先确认最终拼出的地址能否从当前后端环境直接访问。

注意：

- “浏览器里能打开”不代表后端所在机器一定能打开
- 云上部署时尤其要注意域名、回源和防火墙差异

## 三、最常见问题 2：图片地址来自私有仓库

你当前的文章图片最初来源是私有 GitHub 仓库，这里要特别注意：

- 如果最终写进 Markdown 的还是需要鉴权的私有地址
- 后端无法直接下载
- OCR / caption 就会失败

推荐做法：

- Markdown 里最终保存博客可公开访问的图片地址
- 或者保存经过 CDN / 对象存储代理后的稳定地址

不要把必须带 GitHub 登录态才能访问的地址直接交给 OCR 链路。

## 四、最常见问题 3：没有百炼 Key

如果未配置：

- `OPENAI_API_KEY`

当前实现会进入回退模式：

- 不做真实 OCR
- 不做真实 caption
- 用图片 alt、文件名和前后文拼一个启发式说明

这能保证链路可跑，但语义效果会明显下降。

## 五、最常见问题 4：图片已经入库，但回答里没出现

这通常不是图片提取失败，而是以下几种情况：

1. 图片特征没被召回
2. 被文本结果挤掉
3. 被图片预算裁掉
4. 前端没展示 `related_images`

### 优先检查

- `CHAT_IMAGE_TOP_K`
- `CHAT_CONTEXT_IMAGE_TOKENS`
- `related_images` 是否被前端忽略

## 六、最常见问题 5：OCR 内容太长，拖垮上下文

教程类截图可能包含大量界面文字，如果 OCR 原文过长，会带来两个问题：

- 成本上升
- 反而淹没真正重要的信息

当前实现的缓解方式：

- 对 OCR 原文做摘要截断
- 给图片文本单独预算

如果仍然不稳，优先调整：

- `CHAT_CONTEXT_IMAGE_TOKENS`
- `IMAGE_OCR_MAX_PIXELS`

## 七、检查哪张图片是否真的入库

当前落库主要涉及：

- `rag_images`
- `rag_image_features`

重点字段：

- `source_url`
- `title_path`
- `status`
- `caption_text`
- `ocr_text_summary`
- `feature_summary`

### 经验判断

- `status=succeeded`
  说明真实 OCR / caption 跑通了

- `status=fallback`
  说明走了本地回退说明

如果大量图片都是 `fallback`，优先检查：

- 百炼 Key
- 图片访问权限
- 超时配置

## 八、前端展示层面的误判

有时候后端已经返回了图片，但前端没有正确展示，会被误判成“后端没召回图片”。

联调时至少确认：

- `related_images` 是否非空
- `url` 是否可直接用于 `<img src>`
- `caption` 是否展示出来
- `source_slug` / `title_path` 是否用于说明来源

## 九、推荐排查顺序

1. 看文章 Markdown 中图片地址
2. 看 `BLOG_PUBLIC_BASE_URL`
3. 看 `rag_image_features.status`
4. 看 `feature_summary` 是否合理
5. 看 `related_images` 是否返回
6. 看前端是否真的渲染了这些字段
