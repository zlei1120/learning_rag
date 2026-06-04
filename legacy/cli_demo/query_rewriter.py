"""
查询重写模块

实现多种查询重写策略来提升检索召回率：
- 多路查询生成
- HyDE (假设文档嵌入)
- 查询扩展
"""

from typing import List, Optional
from loguru import logger

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from config import Config, get_config

class QueryRewriter:
    """
    查询重写器
    
    通过多种策略改写用户查询，提升检索效果。
    """
    
    # 多路查询生成提示词
    MULTI_QUERY_PROMPT = """你是一个专业的搜索查询优化专家。
请根据用户的原始问题，生成 3 个不同角度的搜索查询。
这些查询应该：
1. 保持原始问题的核心意图
2. 使用不同的表达方式
3. 可能包含同义词或相关概念

原始问题：{question}

请输出 3 个改写后的查询，每行一个，不要编号："""

    # HyDE 提示词：生成假设答案
    HYDE_PROMPT = """请针对以下问题，写一段简短的假设性回答（约 50-100 字）。
这个回答应该像是从一份专业文档中摘录的内容。

问题：{question}

假设回答："""
    def __init__(self, config: Config):

        kwargs = {
            "model": config.model_name,
            "api_key": config.openai_api_key,
            "temperature": 0.7,
        }
        if config.openai_base_url:
            kwargs["base_url"] = config.openai_base_url
        self.llm =  ChatOpenAI(**kwargs)
        logger.info("查询重写器初始化完成，使用模型：{}", config.model_name)
    def generate_multi_queries(self, question: str) -> List[str]:
        """使用多路查询生成策略改写查询"""
        prompt = ChatPromptTemplate.from_template(self.MULTI_QUERY_PROMPT)
        prompt_value = prompt.invoke({"question": question})
        response = self.llm.invoke(prompt_value)
        content = StrOutputParser().invoke(response)
        return [line.strip() for line in content.splitlines() if line.strip()]
    def generate_hyde_query(self, question: str) -> str:
        """使用 HyDE 策略生成假设答案作为查询的一部分"""
        prompt = ChatPromptTemplate.from_template(self.HYDE_PROMPT)
        prompt_value = prompt.invoke({"question": question})
        response = self.llm.invoke(prompt_value)
        return StrOutputParser().invoke(response).strip()