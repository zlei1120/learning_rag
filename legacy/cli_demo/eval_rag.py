"""
LangSmith 标准化评估。

"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from langsmith import Client
from langchain_openai import ChatOpenAI

from chunker import SemanticChunker
from config import get_config
from file_loader import FileLoader
from multi_functional_chain import MutiFunctionalRAGChain
from vector import VectorStoreManager


DATASET_NAME = "learning-rag-light-eval"
EVAL_CHROMA_DIR = "./data/eval_chroma_db"


EVAL_EXAMPLES = [
    {
        "inputs": {
            "question": "极光 X1 智能温控咖啡壶的容量、额定功率和温控范围分别是多少？"
        },
        "outputs": {
            "answer": "容量为 1.0L，额定功率为 1200W，温控范围为 40°C 到 100°C，并且每 1°C 可调。",
            "expected_source": "测试.txt",
            "required_keywords": ["1.0L", "1200W", "40°C", "100°C"],
        },
    },
    {
        "inputs": {"question": "极光 X1 首次使用前应该怎么清洁？"},
        "outputs": {
            "answer": "首次使用前应加入清水至最大水位线，煮沸一次后倒掉，用来清洁内部管路。",
            "expected_source": "测试.txt",
            "required_keywords": ["最大水位线", "煮沸一次", "倒掉", "内部管路"],
        },
    },
    {
        "inputs": {"question": "宫保鸡丁简易版本里，鸡丁需要如何腌制？"},
        "outputs": {
            "answer": "鸡丁中加入盐 2g、老抽酱油 5g、料酒 15g、淀粉 15g 搅拌均匀，再缓慢加入部分葱姜水搅拌至粘手，密封后放入冰箱腌制 1 小时。",
            "expected_source": "宫保鸡丁.md",
            "required_keywords": ["盐 2g", "老抽酱油 5g", "料酒 15g", "淀粉 15g", "葱姜水", "1 小时"],
        },
    },
    {
        "inputs": {"question": "极光 X1 的 App 连接失败通常有哪些原因和解决方法？"},
        "outputs": {
            "answer": "常见原因是手机连接了 5G Wi-Fi 或蓝牙未开启。解决方法是切换至 2.4G Wi-Fi，并打开手机蓝牙、靠近设备。",
            "expected_source": "测试.txt",
            "required_keywords": ["5G Wi-Fi", "2.4G", "蓝牙", "靠近设备"],
        },
    },
    {
        "inputs": {"question": "做宫保鸡丁时，水淀粉怎么调？什么时候加入？"},
        "outputs": {
            "answer": "用淀粉 10g 加 50g 清水调成水淀粉，在后段加入锅中翻炒均匀，并收汁到想要的浓度。",
            "expected_source": "宫保鸡丁.md",
            "required_keywords": ["淀粉 10g", "50g 清水", "水淀粉", "收汁"],
        },
    },
]


_BASE_CHAIN: MutiFunctionalRAGChain | None = None
_JUDGE_LLM: ChatOpenAI | None = None





def get_eval_examples() -> list[dict[str, Any]]:
    """按 EVAL_LIMIT 截取评估样例，默认先跑 3 条。"""
    limit = int(os.getenv("EVAL_LIMIT", "3"))
    return EVAL_EXAMPLES[:limit]


def ensure_dataset(client: Client) -> None:
    """创建或复用 LangSmith 数据集。"""
    examples = get_eval_examples()
    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
        existing_count = sum(1 for _ in client.list_examples(dataset_id=dataset.id))
        if existing_count >= len(examples):
            print(f"已复用数据集：{DATASET_NAME}，当前样例数：{existing_count}")
            return
    else:
        client.create_dataset(
            dataset_name=DATASET_NAME,
            description="learning_rag 的轻量标准评估集，样例来自 data/ 目录。",
        )

    client.create_examples(dataset_name=DATASET_NAME, examples=examples)
    print(f"已写入评估样例：{len(examples)} 条")


def build_base_chain() -> MutiFunctionalRAGChain:
    """构建本地 RAG 核心链路。"""
    global _BASE_CHAIN
    if _BASE_CHAIN is not None:
        return _BASE_CHAIN

    config = get_config()
    config.chroma_persist_dir = EVAL_CHROMA_DIR
    config.top_k = min(config.top_k, 3)

    loader = FileLoader()
    documents = loader.load("./data/")
    if not documents:
        raise ValueError("data/ 目录下没有可评估的文档")

    chunker = SemanticChunker(config=config, breakpoint_threshold=0.6)
    chunks = chunker.split_documents(documents)

    vector = VectorStoreManager(config)
    existing_count = vector.vectorstore._collection.count()
    if existing_count > 0:
        print(f"已复用评估向量库：{EVAL_CHROMA_DIR}，当前文档数：{existing_count}")
    else:
        vector.add_documents(chunks)

    _BASE_CHAIN = MutiFunctionalRAGChain(
        documents=chunks,
        config=config,
        vector_store_manager=vector,
    )
    return _BASE_CHAIN


def target(inputs: dict[str, Any]) -> dict[str, Any]:
    """LangSmith evaluate 会调用这个函数。"""
    question = inputs["question"]

    result = build_base_chain().ask_with_source(question)
    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
    }


def answer_not_empty(outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    """评估答案是否为空。"""
    answer = outputs.get("answer", "").strip()
    return {
        "key": "answer_not_empty",
        "score": bool(answer),
        "comment": "答案非空" if answer else "答案为空",
    }


def source_hit(outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    """评估来源是否命中预期文档。"""
    expected_source = reference_outputs.get("expected_source", "")
    source_names = [source.get("source", "") for source in outputs.get("sources", [])]
    return {
        "key": "source_hit",
        "score": expected_source in source_names,
        "comment": f"期望来源：{expected_source}；实际来源：{source_names}",
    }


def get_judge_llm() -> ChatOpenAI:
    """创建大模型裁判。"""
    global _JUDGE_LLM
    if _JUDGE_LLM is not None:
        return _JUDGE_LLM

    config = get_config()
    params = {
        "model": os.getenv("EVAL_JUDGE_MODEL", config.model_name),
        "api_key": config.openai_api_key,
        "temperature": 0, # 一个冰冷的裁判
    }
    if config.openai_base_url:
        params["base_url"] = config.openai_base_url

    _JUDGE_LLM = ChatOpenAI(**params)
    return _JUDGE_LLM


def parse_judge_result(content: str) -> tuple[float, str]:
    """解析裁判模型返回的 JSON。"""
    json_match = re.search(r"\{.*\}", content, flags=re.S)
    if not json_match:
        return 0.0, f"裁判模型没有返回 JSON：{content}"

    try:
        data = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return 0.0, f"裁判模型 JSON 解析失败：{content}"

    score = float(data.get("score", 0.0))
    score = max(0.0, min(1.0, score))
    comment = str(data.get("comment", "")).strip()
    return score, comment


def answer_correctness(
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    reference_outputs: dict[str, Any],
) -> dict[str, Any]:
    """用大模型评估实际回答与标准答案的语义一致性。"""
    prompt = f"""
你是一个严格但公平的 RAG 问答评估员。

请根据【用户问题】、【标准答案】和【实际回答】判断实际回答是否正确。

评分规则：
- 1.0：关键事实完全正确，允许措辞不同、顺序不同。
- 0.7：主要事实正确，但有轻微遗漏。
- 0.4：只答对一部分，或者遗漏了重要条件。
- 0.0：关键事实错误、答非所问，或编造了标准答案没有的信息。

注意：
- 不要因为表达方式不同而扣分。
- 数字、单位、步骤、限制条件错误要明显扣分。
- 只返回 JSON，不要输出 Markdown。

【用户问题】
{inputs.get("question", "")}

【标准答案】
{reference_outputs.get("answer", "")}

【实际回答】
{outputs.get("answer", "")}

请返回：
{{"score": 0.0到1.0之间的小数, "comment": "中文评估理由"}}
"""

    response = get_judge_llm().invoke(prompt)
    content = str(getattr(response, "content", response))
    score, comment = parse_judge_result(content)
    return {
        "key": "answer_correctness",
        "score": score,
        "comment": comment,
    }


def run_eval() -> None:
    """运行 LangSmith 标准化评估。"""
    client = Client()
    ensure_dataset(client)

    results = client.evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[answer_not_empty, source_hit, answer_correctness],
        experiment_prefix="learning-rag-light",
        description="轻量 RAG 标准评估：使用大模型裁判评估回答正确性。",
        metadata={
            "app": "learning_rag",
            "dataset": DATASET_NAME,
            "eval_limit": len(get_eval_examples()),
            "target": "MutiFunctionalRAGChain",
            "judge_model": os.getenv("EVAL_JUDGE_MODEL", get_config().model_name),
        },
        max_concurrency=1,
    )
    print(results)


if __name__ == "__main__":
    run_eval()
