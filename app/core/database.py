from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """SQLAlchemy 模型基类。"""

    metadata = MetaData(schema=settings.rag_schema)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """按需创建数据库引擎，避免模块导入时就绑定环境状态。"""
    settings = get_settings()
    return create_engine(settings.database_url, future=True, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """返回当前数据库配置对应的会话工厂。"""
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database_health() -> str:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "unavailable"


def ensure_rag_storage_ready() -> None:
    """确保 RAG 所需 schema 和表结构在目标数据库中存在。"""
    import app.models  # noqa: F401

    engine = get_engine()
    schema_name = Base.metadata.schema
    with engine.begin() as conn:
        if schema_name:
            # 这里不用 SQLAlchemy 的 CreateSchema(if_not_exists=True)，
            # 避免在当前 PostgreSQL/驱动组合下触发重复创建 schema 的唯一约束异常。
            quoted_schema = conn.dialect.identifier_preparer.quote_identifier(schema_name)
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}"))
        Base.metadata.create_all(bind=conn)


def reset_database_cache() -> None:
    """清空数据库相关缓存，方便测试场景重新装载连接配置。"""
    get_session_factory.cache_clear()
    get_engine.cache_clear()
