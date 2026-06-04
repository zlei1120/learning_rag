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
        return OpenAIEmbeddings(**kwargs,chunk_size=ALIYUN_EMBEDDING_BATCH_SIZE) # 注意，百炼平台的一定加上，限制10个超过或者不写，当文档长度超过模型限制时会报错
