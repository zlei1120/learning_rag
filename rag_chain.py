"""
    构建rag链

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
# from simpleRAG.query import QueryRewriter
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
class RAGChain:
    """
    RAG 问答链
    
    组装检索器、Prompt 和 LLM，实现端到端的问答功能。
    """
    def __init__(
        self,
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
        self.chain = self.build_chain()
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
    def build_chain(self):
        """构建 RAG 链"""
        retriever = self.vector_store_manager.as_retriever()
        chain =  {
                "context": retriever  | self._format_docs,
                "question": RunnablePassthrough()
                } | self.prompt_template | self.llm | StrOutputParser()
        return chain
    def answer_question_fromDocs(self, question: str, context: str) -> str: 
        # 这里已经在 ask()/ask_with_source() 中手动检索并格式化好了 context，
        # 所以直接走 prompt -> llm -> parser，不再让 retriever 重复检索。
        prompt_value = self.prompt_template.invoke({"question": question, "context": context})
        response = self.llm.invoke(prompt_value)
        return StrOutputParser().invoke(response)
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
    def ask(self,question:str) -> str:
        # logger.info(f"收到问题：{question}")
        # docs = self.vector_store_manager.similarity_search(question)
        # context = self._format_docs(docs)
        # res = self.answer_question_fromDocs(question,context)

        
        res= self.chain.invoke(question)
        return res
        # 手动
    def ask_with_source(self,question:str)->  Dict[str, Any] :
        logger.info(f"收到问题：{question}")
        docs = self.vector_store_manager.similarity_search(question)
        context = self._format_docs(docs)
        res = self.answer_question_fromDocs(question,context)
        sources = [
            {
                "content": doc.page_content[:200] + "...",
                "source": doc.metadata.get("file_name", "未知"),
                "metadata": doc.metadata
            }
            for doc in docs
        ]
        return {
            "answer":res,
            "sources":sources,
            "question":question
        }