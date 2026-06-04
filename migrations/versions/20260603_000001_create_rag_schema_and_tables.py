"""创建 RAG 基础表结构

Revision ID: 20260603_000001
Revises:
Create Date: 2026-06-03 22:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = "20260603_000001"
down_revision = None
branch_labels = None
depends_on = None

RAG_SCHEMA = "rag"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {RAG_SCHEMA}")

    op.create_table(
        "rag_documents",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("source_post_id", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("series", sa.String(length=255), nullable=True),
        sa.Column("series_order", sa.Integer(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=RAG_SCHEMA,
    )
    op.create_index(
        "ix_rag_documents_source_post_id",
        "rag_documents",
        ["source_post_id"],
        unique=True,
        schema=RAG_SCHEMA,
    )
    op.create_index("ix_rag_documents_slug", "rag_documents", ["slug"], unique=True, schema=RAG_SCHEMA)

    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("document_id", sa.String(length=32), nullable=False),
        sa.Column("section_id", sa.String(length=128), nullable=True),
        sa.Column("title_path", sa.String(length=512), nullable=True),
        sa.Column("section_title", sa.String(length=255), nullable=True),
        sa.Column("heading_level", sa.Integer(), nullable=True),
        sa.Column("section_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("child_chunk_index", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=True),
        sa.Column("has_images", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["document_id"], [f"{RAG_SCHEMA}.rag_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=RAG_SCHEMA,
    )
    op.create_index(
        "ix_rag_chunks_document_chunk",
        "rag_chunks",
        ["document_id", "chunk_index"],
        unique=False,
        schema=RAG_SCHEMA,
    )
    op.create_index("ix_rag_chunks_section_id", "rag_chunks", ["section_id"], unique=False, schema=RAG_SCHEMA)
    op.create_index(
        "ix_rag_chunks_content_hash",
        "rag_chunks",
        ["content_hash"],
        unique=False,
        schema=RAG_SCHEMA,
    )

    op.create_table(
        "rag_embeddings",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("chunk_id", sa.String(length=32), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
        sa.Column("embedding_version", sa.String(length=64), nullable=False, server_default=sa.text("'v1'")),
        sa.Column("embedding_vector", Vector(dim=None), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["chunk_id"], [f"{RAG_SCHEMA}.rag_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=RAG_SCHEMA,
    )
    op.create_index("ix_rag_embeddings_chunk_id", "rag_embeddings", ["chunk_id"], unique=False, schema=RAG_SCHEMA)
    op.create_index(
        "ix_rag_embeddings_model_version",
        "rag_embeddings",
        ["embedding_model", "embedding_version"],
        unique=False,
        schema=RAG_SCHEMA,
    )

    op.create_table(
        "rag_images",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("document_id", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("alt_text", sa.Text(), nullable=True),
        sa.Column("markdown_ref", sa.Text(), nullable=True),
        sa.Column("title_path", sa.String(length=512), nullable=True),
        sa.Column("section_id", sa.String(length=128), nullable=True),
        sa.Column("image_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("neighbor_text_before", sa.Text(), nullable=True),
        sa.Column("neighbor_text_after", sa.Text(), nullable=True),
        sa.Column("image_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["document_id"], [f"{RAG_SCHEMA}.rag_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=RAG_SCHEMA,
    )
    op.create_index(
        "ix_rag_images_normalized_url",
        "rag_images",
        ["normalized_url"],
        unique=False,
        schema=RAG_SCHEMA,
    )

    op.create_table(
        "rag_image_features",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("image_id", sa.String(length=32), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("ocr_text_summary", sa.Text(), nullable=True),
        sa.Column("caption_text", sa.Text(), nullable=True),
        sa.Column("feature_summary", sa.Text(), nullable=True),
        sa.Column("ocr_model", sa.String(length=128), nullable=True),
        sa.Column("caption_model", sa.String(length=128), nullable=True),
        sa.Column("feature_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("token_estimate", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["image_id"], [f"{RAG_SCHEMA}.rag_images.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=RAG_SCHEMA,
    )
    op.create_index(
        "ix_rag_image_features_feature_hash",
        "rag_image_features",
        ["feature_hash"],
        unique=False,
        schema=RAG_SCHEMA,
    )

    op.create_table(
        "rag_chunk_images",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("chunk_id", sa.String(length=32), nullable=False),
        sa.Column("image_id", sa.String(length=32), nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("distance_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["chunk_id"], [f"{RAG_SCHEMA}.rag_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_id"], [f"{RAG_SCHEMA}.rag_images.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=RAG_SCHEMA,
    )

    op.create_table(
        "rag_ingest_jobs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("target_post_id", sa.String(length=64), nullable=True),
        sa.Column("target_slug", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("trigger_source", sa.String(length=64), nullable=False, server_default=sa.text("'api'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=RAG_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("rag_ingest_jobs", schema=RAG_SCHEMA)
    op.drop_table("rag_chunk_images", schema=RAG_SCHEMA)
    op.drop_index("ix_rag_image_features_feature_hash", table_name="rag_image_features", schema=RAG_SCHEMA)
    op.drop_table("rag_image_features", schema=RAG_SCHEMA)
    op.drop_index("ix_rag_images_normalized_url", table_name="rag_images", schema=RAG_SCHEMA)
    op.drop_table("rag_images", schema=RAG_SCHEMA)
    op.drop_index("ix_rag_embeddings_model_version", table_name="rag_embeddings", schema=RAG_SCHEMA)
    op.drop_index("ix_rag_embeddings_chunk_id", table_name="rag_embeddings", schema=RAG_SCHEMA)
    op.drop_table("rag_embeddings", schema=RAG_SCHEMA)
    op.drop_index("ix_rag_chunks_content_hash", table_name="rag_chunks", schema=RAG_SCHEMA)
    op.drop_index("ix_rag_chunks_section_id", table_name="rag_chunks", schema=RAG_SCHEMA)
    op.drop_index("ix_rag_chunks_document_chunk", table_name="rag_chunks", schema=RAG_SCHEMA)
    op.drop_table("rag_chunks", schema=RAG_SCHEMA)
    op.drop_index("ix_rag_documents_slug", table_name="rag_documents", schema=RAG_SCHEMA)
    op.drop_index("ix_rag_documents_source_post_id", table_name="rag_documents", schema=RAG_SCHEMA)
    op.drop_table("rag_documents", schema=RAG_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {RAG_SCHEMA} CASCADE")
