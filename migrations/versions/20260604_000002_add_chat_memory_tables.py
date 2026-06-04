"""新增会话、消息和记忆表

Revision ID: 20260604_000002
Revises: 20260603_000001
Create Date: 2026-06-04 09:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260604_000002"
down_revision = "20260603_000001"
branch_labels = None
depends_on = None

RAG_SCHEMA = "rag"


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_key", sa.String(length=128), nullable=True),
        sa.Column("session_scope", sa.String(length=32), nullable=False, server_default=sa.text("'anonymous'")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checkpoint_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        schema=RAG_SCHEMA,
    )
    op.create_index("ix_chat_sessions_session_id", "chat_sessions", ["session_id"], unique=True, schema=RAG_SCHEMA)

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("chat_session_id", sa.String(length=32), nullable=False),
        sa.Column("message_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_summary", sa.Text(), nullable=True),
        sa.Column("source_payload_json", sa.JSON(), nullable=True),
        sa.Column("budget_included", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("trimmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("token_estimate", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["chat_session_id"], [f"{RAG_SCHEMA}.chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=RAG_SCHEMA,
    )
    op.create_index(
        "ix_chat_messages_session_message",
        "chat_messages",
        ["chat_session_id", "message_index"],
        unique=False,
        schema=RAG_SCHEMA,
    )

    op.create_table(
        "memory_records",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("chat_session_id", sa.String(length=32), nullable=True),
        sa.Column("user_key", sa.String(length=128), nullable=True),
        sa.Column("memory_scope", sa.String(length=32), nullable=False, server_default=sa.text("'session'")),
        sa.Column("memory_type", sa.String(length=32), nullable=False, server_default=sa.text("'summary'")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("importance_score", sa.Float(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["chat_session_id"], [f"{RAG_SCHEMA}.chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=RAG_SCHEMA,
    )
    op.create_index(
        "ix_memory_records_session_scope",
        "memory_records",
        ["chat_session_id", "memory_scope", "memory_type"],
        unique=False,
        schema=RAG_SCHEMA,
    )
    op.create_index(
        "ix_memory_records_content_hash",
        "memory_records",
        ["content_hash"],
        unique=False,
        schema=RAG_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_memory_records_content_hash", table_name="memory_records", schema=RAG_SCHEMA)
    op.drop_index("ix_memory_records_session_scope", table_name="memory_records", schema=RAG_SCHEMA)
    op.drop_table("memory_records", schema=RAG_SCHEMA)
    op.drop_index("ix_chat_messages_session_message", table_name="chat_messages", schema=RAG_SCHEMA)
    op.drop_table("chat_messages", schema=RAG_SCHEMA)
    op.drop_index("ix_chat_sessions_session_id", table_name="chat_sessions", schema=RAG_SCHEMA)
    op.drop_table("chat_sessions", schema=RAG_SCHEMA)
