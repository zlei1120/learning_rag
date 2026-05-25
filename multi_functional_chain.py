"""
    构建rag链
    查询重写
    混合检索
    重排序
"""

from typing import List, Optional, Dict, Any
from loguru import logger
from pydantic import SecretStr
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

from config import Config, get_config
from vector import VectorStoreManager
from query_rewriter import QueryRewriter
from hybrid_retriever import HybridRetriever
from reranker import Reranker
# 默认的 RAG 提示模板，包含了对模型能力的描述和回答要求
DEFAULT_RAG_PROMPT = """
你是一个能够进行深度阅读理解、总结和分析的中文助手。

请基于参考文档回答用户问题，但允许你进行：
- 归纳总结
- 风格分析
- 观点选择
- 句子评价
- 合理推断（必须基于文档给出的内容）

禁止编造超出文档不存在的事实信息，但允许在文中信息基础上做解释性、分析性和判断性的扩展。

如果文档完全无关，才回答："根据提供的文档，我无法回答这个问题"。

【参考文档】
{context}

【用户问题】
{question}

请用中文回答：
"""
reranker_model: str = "bge-reranker-base"
class MutiFunctionalRAGChain:
    """
    RAG 问答链
    
    组装检索器、Prompt 和 LLM，实现端到端的问答功能。
    """
    def __init__(
        self,
        documents: Optional[List[Document]] = None,
        config: Optional[Config] = None,
        vector_store_manager: Optional[VectorStoreManager] = None,
        llm: Optional[ChatOpenAI] = None,
        prompt_template: Optional[str] = None,
    ):
        """
        初始化 RAGChain 实例
        
        Args:
            config: 配置对象，如果为 None 则从环境变量加载
            vector_store_manager: 向量存储管理器实例，如果为 None 则创建默认实例
            llm: 语言模型实例，如果为 None 则创建默认 ChatOpenAI 实例
            prompt_template: RAG 提示模板字符串，如果为 None 则使用默认模板
        """
        self.config = config or get_config()
        self.vector_store_manager = vector_store_manager or VectorStoreManager(self.config)
        self.llm = self._create_llm()
        self.prompt_template =ChatPromptTemplate.from_template(prompt_template or DEFAULT_RAG_PROMPT)
        self.query_rewriter = QueryRewriter(self.config)
        self.hybrid_retriever = HybridRetriever(
            documents=documents,
            vectorstore_manager=self.vector_store_manager,
            config=self.config,
            bm25_weight=0.5,
            vector_weight=0.5,
        )
        self._reranker = Reranker(
            model_name=reranker_model,
            config=self.config,
        )
    def _create_llm(self) -> ChatOpenAI:
        """创建 ChatOpenAI 实例"""
        params={
            "model": self.config.model_name,
            "temperature": 0.2,
            "api_key": SecretStr(self.config.openai_api_key),
        }
        if self.config.openai_base_url:
            params["base_url"] = self.config.openai_base_url
        return ChatOpenAI(
            **params
        )
    def _format_docs(self, docs: List[Document]) -> str:
        """
        格式化检索到的文档
        
        Args:
            docs: 文档列表
            
        Returns:
            str: 格式化后的文档文本
        """
        formatted = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("file_name", "未知来源")
            content = doc.page_content.strip()
            formatted.append(f"[文档 {i}] (来源: {source})\n{content}")
        # print("formatted__________",formatted)
        return "\n\n---\n\n".join(formatted)
    def _retrieve_docs(self, query: list[str]) -> List[Document]:
        """检索相关文档"""
        resdocs = []
        seen_doc_keys = set()  # 用于去重，记录已经添加过的文档键
        for q in query:
            # 直接进行混合搜索 检索器里面虽然也有去重逻辑，但是那是针对一个查询检索出来的文档
            # 当时多query时 外部所有的检索结果也需要去重
            # 增加每个查询的检索数量，确保覆盖更多内容
            docs = self.hybrid_retriever.search(q, k=10)
            for doc in docs:
                # 去重是因为有多query时可能会检索到重复的文档，hash(doc.page_content) 作为文档的唯一标识
                doc_key = hash(doc.page_content)
                if doc_key not in seen_doc_keys:
                    seen_doc_keys.add(doc_key)
                    resdocs.append(doc)
        return resdocs
    
    def ask(self, question: str) -> str:
        """处理用户问题，返回答案"""
        logger.info(f"收到问题：{question}")
        querys = self.query_rewriter.generate_multi_queries(question)
        # 将原始问题也加入检索查询列表，提高召回率
        querys_with_original = [question] + querys
        logger.info(f"生成的多路查询（含原始问题）：{querys_with_original}")
        
        # docs = self.vector_store_manager.similarity_search(question)
        docs = self._retrieve_docs(querys_with_original)
        # 增加重排序后的文档数量，为LLM提供更多上下文
        reranked = self._reranker.rerank(question, docs, top_k=self.config.top_k)
        docs = [doc for doc, _ in reranked]
        context = self._format_docs(docs)
        prompt = self.prompt_template.format(context=context, question=question)
        response = self.llm.invoke(prompt)
        answer = StrOutputParser().invoke(response)
        return answer
    
    def ask_with_source(self, question: str) -> Dict[str, Any]:
        """处理用户问题，返回答案和参考来源"""
        logger.info(f"收到问题：{question}")
        querys = self.query_rewriter.generate_multi_queries(question)
        # 将原始问题也加入检索查询列表，提高召回率
        querys_with_original = [question] + querys
        logger.info(f"生成的多路查询（含原始问题）：{querys_with_original}")
        
        # 检索文档
        docs = self._retrieve_docs(querys_with_original)
        logger.info(f"检索到 {len(docs)} 个文档")
        
        # 重排序
        reranked = self._reranker.rerank(question, docs, top_k=len(docs))
        docs = [doc for doc, _ in reranked]
        logger.info(f"重排序后保留 {len(docs)} 个文档")
        
        # 格式化上下文
        context = self._format_docs(docs)
        prompt = self.prompt_template.format(context=context, question=question)
        
        # 生成答案
        response = self.llm.invoke(prompt)
        answer = StrOutputParser().invoke(response)
        
        # 构建来源信息
        sources = [
            {
                "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                "source": doc.metadata.get("file_name", "未知"),
                "metadata": doc.metadata
            }
            for doc in docs
        ]
        
        return {
            "answer": answer,
            "sources": sources,
            "question": question
        }
