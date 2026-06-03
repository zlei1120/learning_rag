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
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    chat_model: str = Field(default="qwen3.6-plus", alias="CHAT_MODEL")
    embedding_model: str = Field(default="text-embedding-v4", alias="EMBEDDING_MODEL")
    rerank_model: str = Field(default="qwen3-rerank", alias="RERANK_MODEL")
    ocr_model: str = Field(default="qwen-vl-ocr", alias="OCR_MODEL")
    image_caption_model: str = Field(default="qwen3.6-flash", alias="IMAGE_CAPTION_MODEL")

    chat_context_max_tokens: int = Field(default=24000, alias="CHAT_CONTEXT_MAX_TOKENS")
    chat_context_recent_messages_tokens: int = Field(default=3000, alias="CHAT_CONTEXT_RECENT_MESSAGES_TOKENS")
    chat_context_summary_tokens: int = Field(default=2000, alias="CHAT_CONTEXT_SUMMARY_TOKENS")
    chat_context_retrieval_tokens: int = Field(default=12000, alias="CHAT_CONTEXT_RETRIEVAL_TOKENS")
    chat_context_image_tokens: int = Field(default=4000, alias="CHAT_CONTEXT_IMAGE_TOKENS")
    chat_context_reserved_output_tokens: int = Field(default=3000, alias="CHAT_CONTEXT_RESERVED_OUTPUT_TOKENS")

    chat_retrieval_top_k: int = Field(default=8, alias="CHAT_RETRIEVAL_TOP_K")
    chat_image_top_k: int = Field(default=3, alias="CHAT_IMAGE_TOP_K")
    chat_enable_parent_chunk_expansion: bool = Field(default=True, alias="CHAT_ENABLE_PARENT_CHUNK_EXPANSION")

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(override=False)
    return Settings()


def reset_settings_cache() -> None:
    """清空配置缓存，方便测试或切换环境变量后重新加载。"""
    get_settings.cache_clear()
