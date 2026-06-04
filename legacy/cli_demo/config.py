import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from loguru import logger


@dataclass
class Config:
    """llm配置信息"""
    openai_api_key: str = "" 
    openai_base_url: Optional[str] = None
    model_name: str = "qwen3.6-plus"
    embedding_model: str = "text-embedding-v4"
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 3
    enable_parent_chunk_expansion: bool = False
    parent_chunk_window_size: int = 4
    chroma_persist_dir: str = "./data/chroma_db"

    @classmethod
    def load_config(cls) -> "Config":
        """从环境变量加载"""
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY") or ""
        return cls(
            openai_api_key=api_key,
            openai_base_url=os.getenv("OPENAI_BASE_URL"),
            model_name=os.getenv("MODEL_NAME", "qwen3.6-plus"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-v4"),
            chunk_size=int(os.getenv("CHUNK_SIZE", "512")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "50")),
            top_k=int(os.getenv("TOP_K", "3")),
            enable_parent_chunk_expansion=os.getenv(
                "ENABLE_PARENT_CHUNK_EXPANSION",
                "false",
            ).lower() in ["1", "true", "yes", "on"],
            parent_chunk_window_size=int(os.getenv("PARENT_CHUNK_WINDOW_SIZE", "4")),
            chroma_persist_dir="./data/chroma_db",
        )

config: Optional[Config] = None


def get_config() -> Config:
    """获取实例"""
    global config
    if config is None:
        config = Config.load_config()
    return config
