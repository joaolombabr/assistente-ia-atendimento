"""Initial migration — create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ────────────────────────────────────────────────────────────────
    channel_enum = postgresql.ENUM(
        "whatsapp", "telegram", "api", "web", name="channelenum", create_type=True
    )
    message_role_enum = postgresql.ENUM(
        "user", "assistant", "system", name="messagerolemenu", create_type=True
    )
    conversation_status_enum = postgresql.ENUM(
        "active", "closed", "transferred", "waiting",
        name="conversationstatusenum", create_type=True
    )
    message_status_enum = postgresql.ENUM(
        "received", "processing", "sent", "failed", "read",
        name="messagestatusenum", create_type=True
    )

    channel_enum.create(op.get_bind())
    message_role_enum.create(op.get_bind())
    conversation_status_enum.create(op.get_bind())
    message_status_enum.create(op.get_bind())

    # ── Table: users ─────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("channel", sa.Enum("whatsapp", "telegram", "api", "web", name="channelenum"), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("phone_number", sa.String(20), nullable=True),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("language_code", sa.String(10), nullable=False, server_default="pt-BR"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "external_id", name="uq_user_channel_external"),
    )
    op.create_index("ix_users_phone", "users", ["phone_number"])
    op.create_index("ix_users_channel", "users", ["channel"])

    # ── Table: conversations ──────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.Enum("whatsapp", "telegram", "api", "web", name="channelenum"), nullable=False),
        sa.Column("status", sa.Enum("active", "closed", "transferred", "waiting", name="conversationstatusenum"), nullable=False, server_default="active"),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_status", "conversations", ["status"])
    op.create_index("ix_conversations_channel", "conversations", ["channel"])

    # ── Table: messages ────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Enum("user", "assistant", "system", name="messagerolemenu"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("received", "processing", "sent", "failed", "read", name="messagestatusenum"), nullable=False, server_default="received"),
        sa.Column("external_message_id", sa.String(200), nullable=True),
        sa.Column("channel_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("model_used", sa.String(50), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("ai_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_role", "messages", ["role"])
    op.create_index("ix_messages_status", "messages", ["status"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])

    # ── Table: audit_logs ─────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(100), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS messagestatusenum")
    op.execute("DROP TYPE IF EXISTS conversationstatusenum")
    op.execute("DROP TYPE IF EXISTS messagerolemenu")
    op.execute("DROP TYPE IF EXISTS channelenum")
