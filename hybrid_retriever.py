"""
混合检索模块

实现 BM25 关键词检索和向量检索的混合策略。

该模块结合了两种植索方法的优势：
- BM25：基于关键词匹配的传统检索算法，对精确匹配效果好
- 向量检索：基于语义相似度的检索，能理解语义关联

通过倒数排名融合（RRF）算法将两种检索结果进行加权融合，
提高检索的准确性和鲁棒性。
"""
import re
from typing import Optional
import jieba
import numpy as np
from langchain_core.documents import Document
from loguru import logger
from rank_bm25 import BM25Okapi
from config import Config, get_config
from vector import VectorStoreManager


class HybridRetriever:
    """结合 BM25 和向量检索的混合检索器。
    
    该类实现了混合检索策略，通过以下步骤完成检索：
    1. 分别执行 BM25 关键词检索和向量语义检索
    2. 对两种检索结果进行加权处理
    3. 使用倒数排名融合（Reciprocal Rank Fusion, RRF）算法合并结果
    4. 返回融合后的Top-K文档
    
    Attributes:
        config: 配置对象，包含检索参数等
        vectorstore_manager: 向量存储管理器，负责向量检索
        bm25_weight: BM25检索结果的权重（0-1之间）
        vector_weight: 向量检索结果的权重（0-1之间）
        _bm25: BM25索引对象
        _documents: 文档列表
        _tokenized_corpus: 分词后的语料库
    """

    def __init__(
        self,
        documents: Optional[list[Document]] = None,
        vectorstore_manager: Optional[VectorStoreManager] = None,
        config: Optional[Config] = None,
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
    ) -> None:
        """初始化混合检索器。
        
        Args:
            documents: 可选的文档列表，用于构建BM25索引
            vectorstore_manager: 向量存储管理器实例，如不提供则自动创建
            config: 配置对象，如不提供则使用默认配置
            bm25_weight: BM25检索权重，默认为0.5
            vector_weight: 向量检索权重，默认为0.5
        """
        self.config = config or get_config()
        self.vectorstore_manager = vectorstore_manager or VectorStoreManager(self.config)
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight

        self._bm25: Optional[BM25Okapi] = None
        self._documents: list[Document] = []
        self._tokenized_corpus: list[list[str]] = []

        if documents:
            self.build_bm25_index(documents)

        logger.info(
            "混合检索器初始化: BM25权重={}, 向量权重={}",
            bm25_weight,
            vector_weight,
        )

    def _tokenize(self, text: str) -> list[str]:
        """对文本进行分词处理。
        
        针对中英文混合文本采用不同的分词策略：
        - 中文：使用 jieba 分词库进行分词
        - 英文和数字：保持完整的单词/数字作为token
        
        Args:
            text: 待分词的原始文本
            
        Returns:
            分词后的token列表
        """
        tokens: list[str] = []
        # 使用正则表达式分离中文和英文/数字部分
        # [\u4e00-\u9fff]+ 匹配连续的中文字符
        # [a-zA-Z0-9]+ 匹配连续的英文字母和数字
        segments = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+", text.lower())

        for segment in segments:
            # 判断是否为中文字符段
            if re.match(r"[\u4e00-\u9fff]", segment):
                # 中文使用jieba分词，去除空字符串
                tokens.extend(token.strip() for token in jieba.lcut(segment) if token.strip())
            else:
                # 英文/数字直接保留为完整token
                tokens.append(segment)

        return tokens

    def build_bm25_index(self, documents: list[Document]) -> None:
        """构建BM25检索索引。
        
        对文档集合进行分词处理，并构建BM25检索模型。
        BM25是一种基于概率检索框架的信息检索算法，
        通过计算查询词与文档的相关性得分进行排序。
        
        Args:
            documents: 用于构建索引的文档列表
        """
        self._documents = documents
        self._tokenized_corpus = [self._tokenize(doc.page_content) for doc in documents]
        self._bm25 = BM25Okapi(self._tokenized_corpus)
        logger.info("BM25 索引构建完成: {} 个文档", len(documents))

    def bm25_search(self, query: str, k: int = 10) -> list[tuple[Document, float]]:
        """执行BM25关键词检索。
        
        基于查询词在文档集合中进行关键词匹配，返回相关性最高的k个文档。
        BM25得分考虑了词频(TF)和逆文档频率(IDF)。
        
        Args:
            query: 查询字符串
            k: 返回结果数量，默认为10
            
        Returns:
            文档和得分的元组列表，按得分降序排列
        """
        if self._bm25 is None:
            logger.warning("BM25 索引未构建")
            return []

        # 对查询语句进行分词
        tokenized_query = self._tokenize(query)
        # 计算查询与所有文档的BM25得分
        scores = self._bm25.get_scores(tokenized_query)
        # 获取得分最高的k个文档索引（降序排列）
        top_indices = np.argsort(scores)[::-1][:k]

        # 构建结果列表，过滤掉得分为0的文档
        results: list[tuple[Document, float]] = [
            (self._documents[int(i)], float(scores[int(i)]))
            for i in top_indices
            if scores[int(i)] > 0
        ]
        return results

    def vector_search(self, query: str, k: int = 10) -> list[tuple[Document, float]]:
        """执行向量语义检索。
        
        通过向量相似度搜索找到语义最相关的文档。
        将距离值转换为相似度得分（距离越小，相似度越高）。
        
        Args:
            query: 查询字符串
            k: 返回结果数量，默认为10
            
        Returns:
            文档和相似度得分的元组列表，按相似度降序排列
        """
        # 从向量存储中获取相似度搜索结果（返回的是距离值）
        results = self.vectorstore_manager.similarity_search_with_score(query, top_k=k)
        processed: list[tuple[Document, float]] = []

        for doc, distance in results:
            # 将距离值转换为相似度得分
            # 使用公式: similarity = 1 / (1 + distance)
            # 距离为0时相似度为1，距离越大相似度越接近0
            similarity = 1.0 / (1.0 + float(distance))
            processed.append((doc, similarity))

        return processed

    def _reciprocal_rank_fusion(
        self,
        result_lists: list[list[tuple[Document, float]]],
        k: int = 60,
    ) -> list[tuple[Document, float]]:
        """使用倒数排名融合（RRF）算法合并多个检索结果。
        
        RRF是一种不依赖具体得分的排名融合方法，只考虑文档在各个
        结果列表中的排名位置。公式：RRF(d) = Σ 1 / (k + rank(d))
        其中k是常数（默认60），用于平滑排名影响。
        
        Args:
            result_lists: 多个检索结果列表的列表
            k: RRF算法的平滑参数，默认为60
            
        Returns:
            融合后的文档和得分元组列表，按RRF得分降序排列
        """
        # 使用文档内容的哈希值作为唯一标识
        doc_scores: dict[int, float] = {}
        doc_map: dict[int, Document] = {}

        for results in result_lists:
            for rank, (doc, _) in enumerate(results):
                # 计算文档内容的哈希值作为唯一key
                doc_key = hash(doc.page_content)

                # 如果是首次遇到该文档，初始化得分和文档映射
                if doc_key not in doc_scores:
                    doc_scores[doc_key] = 0.0
                    doc_map[doc_key] = doc

                # 累加RRF得分：1 / (k + rank + 1)
                # rank从0开始，所以加1使排名从1开始计算
                doc_scores[doc_key] += 1.0 / (k + rank + 1)

        # 按RRF得分降序排序
        sorted_keys = sorted(doc_scores, key=lambda key: doc_scores[key], reverse=True)
        # 返回排序后的文档和得分列表
        return [(doc_map[key], doc_scores[key]) for key in sorted_keys]

    def search(self, query: str, k: Optional[int] = None) -> list[Document]:
        """执行混合检索，返回文档列表。
        
        该方法执行完整的混合检索流程：
        1. 同时进行BM25和向量检索（扩大候选集到top_k*3）
        2. 对两种结果应用权重
        3. 使用RRF算法融合结果
        4. 返回Top-K文档
        
        Args:
            query: 查询字符串
            k: 返回结果数量，如不提供则使用配置中的top_k
            
        Returns:
            检索到的文档列表
        """
        # 确定返回结果数量
        top_k = k if k is not None else self.config.top_k
        # 扩大检索范围，为融合提供足够的候选文档
        # 使用更大的倍数以确保覆盖更多相关内容
        search_k = max(top_k * 10, 20)  # 至少检索20个候选文档

        # 并行执行两种检索
        bm25_results = self.bm25_search(query, k=search_k)
        vector_results = self.vector_search(query, k=search_k)

        # 根据检索结果情况选择融合策略
        if bm25_results and vector_results:
            # 两种检索都有结果，进行加权融合
            weighted_bm25 = [(doc, score * self.bm25_weight) for doc, score in bm25_results]
            weighted_vector = [(doc, score * self.vector_weight) for doc, score in vector_results]
            fused = self._reciprocal_rank_fusion([weighted_bm25, weighted_vector])
        elif bm25_results:
            # 仅BM25有结果
            fused = bm25_results
        elif vector_results:
            # 仅向量检索有结果
            fused = vector_results
        else:
            # 两种检索都无结果
            fused = []

        # 提取文档并截取Top-K结果
        results = [doc for doc, _ in fused[:top_k]]
        logger.info(
            "混合检索完成: BM25={}, 向量={}, 融合后={}",
            len(bm25_results),
            len(vector_results),
            len(results),
        )
        return results

    def search_with_scores(
        self,
        query: str,
        k: Optional[int] = None,
    ) -> list[tuple[Document, float]]:
        """执行混合检索，返回文档和得分的元组列表。
        
        与search方法类似，但同时返回融合后的得分。
        适用于需要查看检索置信度的场景。
        
        Args:
            query: 查询字符串
            k: 返回结果数量，如不提供则使用配置中的top_k
            
        Returns:
            文档和融合得分的元组列表
        """
        # 确定返回结果数量和扩大检索范围
        top_k = k if k is not None else self.config.top_k
        search_k = top_k * 3

        # 执行BM25和向量检索
        bm25_results = self.bm25_search(query, k=search_k)
        vector_results = self.vector_search(query, k=search_k)

        # 根据检索结果情况选择融合策略
        if bm25_results and vector_results:
            # 两种检索都有结果，进行加权融合
            weighted_bm25 = [(doc, score * self.bm25_weight) for doc, score in bm25_results]
            weighted_vector = [(doc, score * self.vector_weight) for doc, score in vector_results]
            fused = self._reciprocal_rank_fusion([weighted_bm25, weighted_vector])
        elif bm25_results:
            # 仅BM25有结果
            fused = bm25_results
        elif vector_results:
            # 仅向量检索有结果
            fused = vector_results
        else:
            # 两种检索都无结果
            fused = []

        # 返回融合后的Top-K结果（包含得分）
        return fused[:top_k]
