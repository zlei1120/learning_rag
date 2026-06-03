# learning_rag

这是一个用于学习 RAG、LangChain、LangGraph 和 LangSmith 的本地知识库问答项目。

当前项目支持：

- 从 `data/` 目录加载文档。
- 对普通文本和 Markdown 文档进行分块。
- 使用向量检索、BM25 和 reranker 做混合检索。
- 使用 `MutiFunctionalRAGChain` 执行本地 RAG 问答。
- 使用 `RAGGraph` 演示 LangGraph 节点编排、工具路由和 interrupt。
- 使用 LangSmith 做 tracing 和标准化评估。

## 环境变量

在 `.env` 中配置模型和 LangSmith 信息：

```env
OPENAI_API_KEY=你的模型服务 Key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen3.6-plus

LANGSMITH_TRACING=true
LANGSMITH_PROJECT=learning
LANGSMITH_API_KEY=你的 LangSmith Key
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

说明：

- `LANGSMITH_TRACING=true` 会开启 LangSmith 自动追踪。
- `LANGSMITH_PROJECT` 是 tracing 所属项目。
- `.env` 已加入 `.gitignore`，不要提交真实 Key。

## 运行问答

```powershell
uv run python main.py
```

运行后可以在命令行输入问题。输入：

```text
sources
```

可以切换是否展示参考来源。

## LangSmith 追踪

只要 `.env` 中配置了 LangSmith 环境变量，LangChain / LangGraph 调用会自动上报 trace。

在 LangSmith 后台可以查看：

- 每次用户输入。
- 检索到的 context。
- LLM 调用的 prompt 和输出。
- LangGraph 每个节点的执行过程。
- 工具路由、检索、重排、生成答案等步骤的耗时。

如果在 `Datasets & Experiments` 中看不到数据集，切到 `All` 视图查找。

## LangSmith 标准化评估

评估脚本是：

```text
eval_rag.py
```

它会自动创建或复用 LangSmith 数据集：

```text
learning-rag-light-eval
```

默认只跑前 3 条样例，方便先验证流程：

```powershell
uv run python eval_rag.py
```

调整样例数量：

```powershell
$env:EVAL_LIMIT="5"
uv run python eval_rag.py
```

指定裁判模型：

```powershell
$env:EVAL_JUDGE_MODEL="qwen3.6-plus"
uv run python eval_rag.py
```

评估脚本使用独立向量库：

```text
data/eval_chroma_db
```

该目录是运行产物，已加入 `.gitignore`。

## 当前评估指标

`eval_rag.py` 当前直接评估 `MutiFunctionalRAGChain`，不经过 LangGraph 工具路由。

评估器包括：

- `answer_not_empty`：检查回答是否为空。
- `source_hit`：检查返回来源是否命中预期文档。
- `answer_correctness`：使用大模型裁判比较实际回答和标准答案，返回 0 到 1 的正确性分数和中文理由。

`answer_correctness` 的评分规则：

- `1.0`：关键事实完全正确，允许措辞不同。
- `0.7`：主要事实正确，但有轻微遗漏。
- `0.4`：只答对一部分，或遗漏重要条件。
- `0.0`：关键事实错误、答非所问，或编造信息。

## 失败样本判断

建议在 LangSmith 的 experiment 中按以下条件过滤失败或边界样本：

```text
answer_correctness < 0.8
```

或者：

```text
source_hit = false
```

一般可以这样分析：

- `source_hit = false` 且 `answer_correctness` 低：优先检查检索和重排。
- `source_hit = true` 但 `answer_correctness` 低：优先检查 prompt 和生成逻辑。
- `answer_not_empty = false`：说明调用链路或模型输出异常。

## 常用开发命令

语法检查：

```powershell
uv run python -m py_compile eval_rag.py
```

查看 Git 状态：

```powershell
git status --short
```
