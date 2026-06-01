import json
from typing import Literal

from langchain_core.output_parsers import StrOutputParser


ToolRoute = Literal["local_rag", "web_search"]


class ToolRouter:
    """根据用户问题选择工具 """
    def __init__(self, llm):
        self.llm = llm
    def route(self, question: str) -> dict[str, str]:
        """让 LLM 判断用户问题应该走本地 RAG，还是走真实互联网搜索。"""
        prompt = f"""
你是一个工具路由器。请判断用户问题应该使用哪个工具。

可选工具：
1. local_rag：查询本地知识库、文档、说明书、菜谱、已有资料。
2. web_search：查询互联网，适合最新信息、实时信息、新闻、价格、今天/现在/最近等问题。

要求：
- 只输出 JSON，不要输出解释性文本。
- route 只能是 "local_rag" 或 "web_search"。
- reason 用一句中文说明原因。

用户问题：
{question}

输出格式：
{{"route": "local_rag", "reason": "用户询问本地文档内容"}}
"""
        response = self.llm.invoke(prompt)
        text = StrOutputParser().invoke(response).strip()
        try:
            data = json.loads(text)
            route = data.get("route", "local_rag")
            reason = data.get("reason", "")
        except json.JSONDecodeError:
            route = "local_rag"
            reason = "工具路由 JSON 解析失败，默认走本地 RAG"
        if route not in ["local_rag", "web_search"]:
            route = "local_rag"
            reason = "工具路由结果不合法，默认走本地 RAG"

        return {"tool_route": route, "route_reason": reason}

