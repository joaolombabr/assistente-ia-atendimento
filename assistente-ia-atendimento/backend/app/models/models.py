"""
Models SQLAlchemy para o sistema de atendimento.
Define as entidades: User, Conversation, Message, AuditLog.
"""

import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────
class ChannelEnum(str, enum.Enum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    API = "api"
    WEB = "web"


class MessageRoleEnum(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    TRANSFERRED = "transferred"  # Transferido para humano
    WAITING = "waiting"


class MessageStatusEnum(str, enum.Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


# ──────────────────────────────────────────────────────────────────────────────
# Mixin para timestamps automáticos
# ──────────────────────────────────────────────────────────────────────────────
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Model: User
# ──────────────────────────────────────────────────────────────────────────────
class User(TimestampMixin, Base):
    """
    Representa um usuário/cliente que interage via WhatsApp ou Telegram.
    Identificado de forma única por channel + external_id.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("channel", "external_id", name="uq_user_channel_external"),
        Index("ix_users_phone", "phone_number"),
        Index("ix_users_channel", "channel"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # ID do usuário no canal externo (WhatsApp number, Telegram user_id)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[ChannelEnum] = mapped_column(Enum(ChannelEnum), nullable=False)

    # Dados do usuário
    name: Mapped[Optional[str]] = mapped_column(String(200))
    phone_number: Mapped[Optional[str]] = mapped_column(String(20))
    username: Mapped[Optional[str]] = mapped_column(String(100))  # @username Telegram
    language_code: Mapped[str] = mapped_column(String(10), default="pt-BR")

    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB)  # Dados extras

    # Relacionamentos
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.channel}:{self.external_id}>"


# ──────────────────────────────────────────────────────────────────────────────
# Model: Conversation
# ──────────────────────────────────────────────────────────────────────────────
class Conversation(TimestampMixin, Base):
    """
    Agrupa as mensagens de uma conversa contínua com um usuário.
    Uma conversa pode ser reaberta ou uma nova pode ser criada.
    """

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_id", "user_id"),
        Index("ix_conversations_status", "status"),
        Index("ix_conversations_channel", "channel"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[ChannelEnum] = mapped_column(Enum(ChannelEnum), nullable=False)
    status: Mapped[ConversationStatusEnum] = mapped_column(
        Enum(ConversationStatusEnum), default=ConversationStatusEnum.ACTIVE
    )

    # Contexto e configuração
    system_prompt: Mapped[Optional[str]] = mapped_column(Text)  # Override do prompt padrão
    title: Mapped[Optional[str]] = mapped_column(String(200))  # Gerado pela IA
    tags: Mapped[Optional[list]] = mapped_column(JSONB)  # ["suporte", "vendas"]

    # Métricas
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relacionamentos
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.id} [{self.status}]>"


# ──────────────────────────────────────────────────────────────────────────────
# Model: Message
# ──────────────────────────────────────────────────────────────────────────────
class Message(TimestampMixin, Base):
    """
    Cada mensagem individual dentro de uma conversa.
    Armazena tanto a mensagem do usuário quanto a resposta da IA.
    """

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_role", "role"),
        Index("ix_messages_status", "status"),
        Index("ix_messages_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[MessageRoleEnum] = mapped_column(Enum(MessageRoleEnum), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MessageStatusEnum] = mapped_column(
        Enum(MessageStatusEnum), default=MessageStatusEnum.RECEIVED
    )

    # Metadados de entrega
    external_message_id: Mapped[Optional[str]] = mapped_column(String(200))  # ID no WhatsApp/TG
    channel_metadata: Mapped[Optional[dict]] = mapped_column(JSONB)  # Raw payload

    # Métricas da IA (apenas para mensagens do assistente)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    model_used: Mapped[Optional[str]] = mapped_column(String(50))
    latency_ms: Mapped[Optional[float]] = mapped_column(Float)
    ai_metadata: Mapped[Optional[dict]] = mapped_column(JSONB)  # finish_reason, etc.

    # Erros (se status == failed)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Relacionamentos
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        preview = self.content[:50] if self.content else ""
        return f"<Message [{self.role}] '{preview}...'>"


# ──────────────────────────────────────────────────────────────────────────────
# Model: AuditLog
# ──────────────────────────────────────────────────────────────────────────────
class AuditLog(Base):
    """
    Log de auditoria para ações importantes no sistema.
    Imutável — nunca atualizado, apenas inserido.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "user", "conversation"
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # "created", "blocked"
    actor: Mapped[Optional[str]] = mapped_column(String(100))  # "system", "admin_user_id"
    details: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
