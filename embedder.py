"""
 将切割的文档转化为向量，供后续的向量数据库使用
"""
from typing import List, Optional
from loguru import logger
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from config import Config, get_config
# 阿里云 Embedding API 的批量大小限制
ALIYUN_EMBEDDING_BATCH_SIZE = 10

settings = get_config()
# 继承自 LangChain 的 Embeddings 抽象基类(必须实现embed_documents，embed_query方法)，适用于阿里云 Embedding API 的批量限制
class BatchedEmbeddings(Embeddings):
    """批量嵌入类，适用于阿里云 Embedding API 的批量限制"""
    def __init__(self, embedding_model: Embeddings, batch_size: int = ALIYUN_EMBEDDING_BATCH_SIZE):
        self.embedding_model = embedding_model
        self.batch_size = batch_size

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """对文本列表进行批量嵌入"""
        all_embeddings = []
        # 纯数学技巧：计算总批次 (用向下取整的符号 //，达到向上取整的效果)
        # 公式：(总长度 + 步长 - 1) // 步长
        # 假设 25 条文本：(25 + 10 - 1) // 10 = 34 // 10 = 3 批
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]  # 获取当前批次的文本 切割文本列表
            batch_embeddings = self.embedding_model.embed_documents(batch)
            all_embeddings.extend(batch_embeddings)
        return all_embeddings
    def embed_query(self, text: str) -> List[float]:
        """对单个查询文本进行嵌入"""
        return self.embedding_model.embed_query(text)
    
class EmbeddingModel:
    """嵌入模型类，封装了 OpenAI 的嵌入功能"""
    def __init__(self, config: Optional[Config] = None):
        """
        初始化嵌入模型
        
        Args:
            config: 配置对象，如果为 None 则从环境变量加载
        """
        self.config = config or get_config()
        self._embeddings: Optional[Embeddings] = None
    # @property 装饰器实现懒加载，只有在第一次访问 embeddings 属性时才创建嵌入模型实例
    @property
    def embeddings(self) -> Embeddings:
        """
        获取嵌入模型实例
        
        Returns:
            Embeddings: LangChain 嵌入模型实例
        """
        if self._embeddings is None:
            self._embeddings = self._create_embeddings()
        return self._embeddings
    def _create_embeddings(self) -> Embeddings:
        """创建嵌入模型实例"""
        logger.info(f"使用嵌入模型: {self.config.embedding_model}")
        kwargs = {
            "model": self.config.embedding_model,
            "api_key": self.config.openai_api_key,
            "check_embedding_ctx_length": False,
        }
        if(self.config.openai_base_url):
            kwargs["base_url"] = self.config.openai_base_url
        return BatchedEmbeddings(embedding_model=OpenAIEmbeddings(**kwargs), batch_size=ALIYUN_EMBEDDING_BATCH_SIZE) # 返回批量嵌入模型实例
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        对文本列表进行嵌入
        
        Args:
            texts: 需要嵌入的文本列表
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        return self.embeddings.embed_documents(texts) # 返回嵌入向量列表
    def embed_query(self, text: str) -> List[float]:
        """对单个查询文本进行嵌入"""
        return self.embeddings.embed_query(text)
