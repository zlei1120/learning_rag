"""
LangGraph 版本的 RAG 流程。

这个文件的目标不是替换 multi_functional_chain.py，而是把现有 RAG 步骤拆成图节点，
方便学习 LangGraph 的状态流转、节点拆分和后续条件分支扩展。
"""

from typing import Any, Literal, NotRequired, TypedDict

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import END, START, StateGraph

from multi_functional_chain import MutiFunctionalRAGChain
from tool_router import ToolRouter
from web_search_tool import WebSearchTool


class RAGState(TypedDict):
    """LangGraph 节点之间共享的状态。"""

    question: str # 用户的初始提问
    queries: NotRequired[list[str]] # 改写后的查询
    docs: NotRequired[list[Document]] # 召回的文档
    context: NotRequired[str] # 格式化后的文档
    answer: NotRequired[str] # 生成的答案
    sources: NotRequired[list[dict[str, Any]]] # 来源信息   
    tool_route: NotRequired[str] # LLM 判断出来的工具路线：local_rag / web_search
    route_reason: NotRequired[str] # 工具路由原因
    web_results: NotRequired[str] # 真实互联网搜索结果


class RAGGraph:
    """把现有 MutiFunctionalRAGChain 包装成 LangGraph 图。"""

    def __init__(self, chain: MutiFunctionalRAGChain):
        self.chain = chain
        self.tool_router = ToolRouter(chain.llm)
        self.web_search_tool = WebSearchTool(chain.llm)
        self.app = self._build_graph()

    def _build_graph(self):
        """构建图结构：查询改写 -> 检索 -> 重排 -> 父子 chunk 扩展 -> 生成答案。"""
        graph = StateGraph(RAGState)

        graph.add_node("route_tool", self._route_tool) # LLM 工具路由节点
        graph.add_node("rewrite_query", self._rewrite_query) # 查询改写节点
        graph.add_node("retrieve_docs", self._retrieve_docs) # 检索节点
        graph.add_node("rerank_docs", self._rerank_docs) # 重排节点
        graph.add_node("expand_parent_chunks", self._expand_parent_chunks) # 父子 chunk 扩展 节点
        graph.add_node("format_context", self._format_context) # 格式化文档
        graph.add_node("generate_answer", self._generate_answer) # 生成答案
        graph.add_node("web_search", self._web_search) # 真实互联网搜索节点
        graph.add_node("answer_from_web", self._answer_from_web) # 基于互联网搜索结果回答
        graph.add_node("build_sources", self._build_sources) # 构建来源信息

        graph.add_edge(START, "route_tool") # 起点（用户输入） -> LLM 判断该用哪个工具
        graph.add_conditional_edges(
            "route_tool",
            self._route_after_tool,
            {
                "local_rag": "rewrite_query",
                "web_search": "web_search",
            },
        )
        graph.add_edge("rewrite_query", "retrieve_docs") # 查询改写 -> 检索
        graph.add_edge("retrieve_docs", "rerank_docs") # 检索 -> 重排
        graph.add_edge("rerank_docs", "expand_parent_chunks") # 重排 -> 父子 chunk 扩展
        graph.add_edge("expand_parent_chunks", "format_context") # 父子 chunk 扩展 -> 格式化文档
        graph.add_edge("format_context", "generate_answer") # 格式化文档 -> 生成答案
        graph.add_edge("generate_answer", "build_sources") # 生成答案 -> 构建来源信息
        graph.add_edge("web_search", "answer_from_web") # 互联网搜索 -> 生成互联网答案
        graph.add_edge("answer_from_web", "build_sources") # 互联网答案 -> 构建来源信息
        graph.add_edge("build_sources", END) # 构建来源信息 -> 终点（返回结果）

        return graph.compile() # 编译图结构

    def _route_tool(self, state: RAGState) -> dict[str, str]:
        """调用工具路由器，判断问题应该走本地 RAG 还是互联网搜索。"""
        return self.tool_router.route(state["question"])

    def _route_after_tool(self, state: RAGState) -> Literal["local_rag", "web_search"]:
        """根据 LLM 路由结果选择下一条边。"""
        if state.get("tool_route") == "web_search":
            return "web_search"
        return "local_rag"

    def _rewrite_query(self, state: RAGState) -> dict[str, list[str]]:
        """把用户问题改写成多路查询，并保留原始问题。"""
        question = state["question"]
        rewritten_queries = self.chain.query_rewriter.generate_multi_queries(question)
        queries = [question] + rewritten_queries
        return {"queries": queries}

    def _retrieve_docs(self, state: RAGState) -> dict[str, list[Document]]:
        """使用现有混合检索器召回候选子 chunk。"""
        docs = self.chain._retrieve_docs(state["queries"])
        return {"docs": docs}

    def _rerank_docs(self, state: RAGState) -> dict[str, list[Document]]:
        """使用 reranker 对候选子 chunk 重排序，并只保留 top_k 个。"""
        reranked = self.chain._reranker.rerank(
            state["question"],
            state["docs"],
            top_k=self.chain.config.top_k,
        )
        docs = [doc for doc, _ in reranked]
        return {"docs": docs}

    def _expand_parent_chunks(self, state: RAGState) -> dict[str, list[Document]]:
        """根据命中的子 chunk，补充有限窗口内的父级上下文。"""
        docs = self.chain._expand_parent_chunks(state["docs"])
        return {"docs": docs}

    def _format_context(self, state: RAGState) -> dict[str, str]:
        """把最终文档列表格式化成 prompt 里的参考文档。"""
        context = self.chain._format_docs(state["docs"])
        return {"context": context}

    def _generate_answer(self, state: RAGState) -> dict[str, str]:
        """调用 LLM 基于上下文生成答案。"""
        prompt = self.chain.prompt_template.format(
            context=state["context"],
            question=state["question"],
        )
        try:
            response = self.chain.llm.invoke(prompt)
            answer = StrOutputParser().invoke(response)
        except Exception as exc:
            answer = (
                "LLM 基于本地文档生成答案失败。\n\n"
                f"失败原因：{exc}\n\n"
                f"本地上下文：\n{state['context']}"
            )
        return {"answer": answer}

    def _web_search(self, state: RAGState) -> dict[str, str]:
        """调用互联网搜索工具。"""
        return {"web_results": self.web_search_tool.search(state["question"])}

    def _answer_from_web(self, state: RAGState) -> dict[str, str]:
        """调用互联网搜索回答工具。"""
        answer = self.web_search_tool.answer(state["question"], state["web_results"])
        return {"answer": answer}

    def _build_sources(self, state: RAGState) -> dict[str, list[dict[str, Any]]]:
        """构建和 ask_with_source 类似的来源信息，方便调试每个答案来自哪些 chunk。"""
        if state.get("tool_route") == "web_search":
            return {
                "sources": [
                    {
                        "content": state.get("web_results", ""),
                        "source": "web_search",
                        "metadata": {
                            "route": state.get("tool_route"),
                            "reason": state.get("route_reason", ""),
                        },
                    }
                ]
            }

        sources = [
            {
                "content": doc.page_content[:200] + "..."
                if len(doc.page_content) > 200
                else doc.page_content,
                "source": doc.metadata.get("file_name", "未知"),
                "metadata": doc.metadata,
            }
            for doc in state["docs"]
        ]
        return {"sources": sources}

    def ask(self, question: str) -> str:
        """只返回答案，行为类似 MutiFunctionalRAGChain.ask。"""
        result = self.app.invoke({"question": question})
        return result["answer"]

    def ask_with_source(self, question: str) -> dict[str, Any]:
        """返回答案和来源，行为类似 MutiFunctionalRAGChain.ask_with_source。"""
        result = self.app.invoke({"question": question})
        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "question": question,
        }
