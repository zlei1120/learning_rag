from __future__ import annotations

from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """FastAPI 后端运行时配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "learning-rag-api"
    app_version: str = "0.1.0"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    debug: bool = False

    database_url: str = Field(
        default="postgresql+psycopg://blog:blog_password@127.0.0.1:5432/blog",
        alias="DATABASE_URL",
    )
    rag_schema: str = Field(default="rag", alias="RAG_SCHEMA")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="OPENAI_BASE_URL",
    )
    rerank_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-api/v1",
        alias="RERANK_BASE_URL",
    )
    blog_public_base_url: str | None = Field(default=None, alias="BLOG_PUBLIC_BASE_URL")
    chat_model: str = Field(default="qwen3.6-plus", alias="CHAT_MODEL")
    embedding_model: str = Field(default="text-embedding-v4", alias="EMBEDDING_MODEL")
    rerank_model: str = Field(default="qwen3-rerank", alias="RERANK_MODEL")
    ocr_model: str = Field(default="qwen-vl-ocr-latest", alias="OCR_MODEL")
    image_caption_model: str = Field(default="qwen-vl-plus", alias="IMAGE_CAPTION_MODEL")

    chat_context_max_tokens: int = Field(default=24000, alias="CHAT_CONTEXT_MAX_TOKENS")
    chat_context_recent_messages_tokens: int = Field(default=3000, alias="CHAT_CONTEXT_RECENT_MESSAGES_TOKENS")
    chat_context_summary_tokens: int = Field(default=2000, alias="CHAT_CONTEXT_SUMMARY_TOKENS")
    chat_context_retrieval_tokens: int = Field(default=12000, alias="CHAT_CONTEXT_RETRIEVAL_TOKENS")
    chat_context_image_tokens: int = Field(default=4000, alias="CHAT_CONTEXT_IMAGE_TOKENS")
    chat_context_reserved_output_tokens: int = Field(default=3000, alias="CHAT_CONTEXT_RESERVED_OUTPUT_TOKENS")
    chat_history_message_limit: int = Field(default=8, alias="CHAT_HISTORY_MESSAGE_LIMIT")
    chat_summary_max_chars: int = Field(default=600, alias="CHAT_SUMMARY_MAX_CHARS")

    chat_retrieval_top_k: int = Field(default=8, alias="CHAT_RETRIEVAL_TOP_K")
    chat_image_top_k: int = Field(default=3, alias="CHAT_IMAGE_TOP_K")
    chat_enable_parent_chunk_expansion: bool = Field(default=True, alias="CHAT_ENABLE_PARENT_CHUNK_EXPANSION")
    chat_parent_chunk_window_size: int = Field(default=2, alias="CHAT_PARENT_CHUNK_WINDOW_SIZE")
    ingest_chunk_size: int = Field(default=900, alias="INGEST_CHUNK_SIZE")
    ingest_chunk_overlap: int = Field(default=120, alias="INGEST_CHUNK_OVERLAP")
    ingest_image_context_window: int = Field(default=220, alias="INGEST_IMAGE_CONTEXT_WINDOW")
    embedding_batch_size: int = Field(default=10, alias="EMBEDDING_BATCH_SIZE")
    image_fetch_timeout_seconds: int = Field(default=20, alias="IMAGE_FETCH_TIMEOUT_SECONDS")
    image_ocr_min_pixels: int = Field(default=3072, alias="IMAGE_OCR_MIN_PIXELS")
    image_ocr_max_pixels: int = Field(default=8388608, alias="IMAGE_OCR_MAX_PIXELS")

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug_value(cls, value: object) -> object:
        """兼容旧环境变量里对调试模式的字符串写法。"""
        if isinstance(value, bool) or value is None:
            return value

        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
            return False
        return value

    @field_validator("openai_base_url", mode="before")
    @classmethod
    def normalize_openai_base_url(cls, value: object) -> str:
        """兼容空字符串配置，默认回退到百炼兼容地址。"""
        if value is None:
            return "https://dashscope.aliyuncs.com/compatible-mode/v1"

        normalized = str(value).strip()
        if not normalized:
            return "https://dashscope.aliyuncs.com/compatible-mode/v1"
        return normalized

    @field_validator("embedding_batch_size", mode="before")
    @classmethod
    def normalize_embedding_batch_size(cls, value: object) -> int:
        """限制向量批量大小，兼容百炼当前单次最多 10 条输入。"""
        if value is None or str(value).strip() == "":
            return 10

        size = int(value)
        if size < 1:
            return 1
        if size > 10:
            return 10
        return size


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(override=False)
    return Settings()


def reset_settings_cache() -> None:
    """清空配置缓存，方便测试或切换环境变量后重新加载。"""
    get_settings.cache_clear()
