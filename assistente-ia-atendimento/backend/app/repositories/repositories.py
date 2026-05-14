"""
Repository layer — abstrai o acesso ao banco de dados.
Cada método é uma operação de banco isolada e testável.
Princípio: Services chamam Repositories, não o SQLAlchemy diretamente.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import structlog
from sqlalchemy import func, select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    ChannelEnum,
    Conversation,
    ConversationStatusEnum,
    Message,
    MessageRoleEnum,
    MessageStatusEnum,
    User,
    AuditLog,
)

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# UserRepository
# ──────────────────────────────────────────────────────────────────────────────
class UserRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(
        self,
        external_id: str,
        channel: ChannelEnum,
        name: Optional[str] = None,
        phone_number: Optional[str] = None,
        username: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Tuple[User, bool]:
        """
        Retorna o usuário existente ou cria um novo.
        Retorna tupla (user, created: bool).
        """
        stmt = select(User).where(
            and_(User.external_id == external_id, User.channel == channel)
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Atualiza dados se necessário
            if name and user.name != name:
                user.name = name
            if phone_number and user.phone_number != phone_number:
                user.phone_number = phone_number
            return user, False

        # Cria novo usuário
        user = User(
            external_id=external_id,
            channel=channel,
            name=name,
            phone_number=phone_number,
            username=username,
            metadata=metadata or {},
        )
        self.db.add(user)
        await self.db.flush()  # Gera o ID sem commit

        logger.info("user.created", user_id=str(user.id), channel=channel, external_id=external_id)
        return user, True

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def block_user(self, user_id: uuid.UUID) -> bool:
        stmt = update(User).where(User.id == user_id).values(is_blocked=True)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def count_total(self) -> int:
        stmt = select(func.count()).select_from(User)
        result = await self.db.execute(stmt)
        return result.scalar_one()


# ──────────────────────────────────────────────────────────────────────────────
# ConversationRepository
# ──────────────────────────────────────────────────────────────────────────────
class ConversationRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_or_create(
        self, user_id: uuid.UUID, channel: ChannelEnum, system_prompt: Optional[str] = None
    ) -> Tuple[Conversation, bool]:
        """
        Busca conversa ativa do usuário ou cria uma nova.
        """
        stmt = (
            select(Conversation)
            .where(
                and_(
                    Conversation.user_id == user_id,
                    Conversation.channel == channel,
                    Conversation.status == ConversationStatusEnum.ACTIVE,
                )
            )
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        conv = result.scalar_one_or_none()

        if conv:
            return conv, False

        conv = Conversation(
            user_id=user_id,
            channel=channel,
            status=ConversationStatusEnum.ACTIVE,
            system_prompt=system_prompt,
        )
        self.db.add(conv)
        await self.db.flush()

        logger.info("conversation.created", conversation_id=str(conv.id), user_id=str(user_id))
        return conv, True

    async def get_with_messages(
        self, conversation_id: uuid.UUID, limit: int = 20
    ) -> Optional[Conversation]:
        """Carrega conversa com histórico de mensagens (eager loading)."""
        stmt = (
            select(Conversation)
            .options(
                selectinload(Conversation.messages),
                selectinload(Conversation.user),
            )
            .where(Conversation.id == conversation_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recent_messages(
        self, conversation_id: uuid.UUID, limit: int = 20
    ) -> List[Message]:
        """Busca as N mensagens mais recentes para contexto da IA."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = result.scalars().all()
        return list(reversed(messages))  # Mais antigas primeiro

    async def increment_message_count(self, conversation_id: uuid.UUID) -> None:
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(message_count=Conversation.message_count + 1)
        )
        await self.db.execute(stmt)

    async def close_conversation(self, conversation_id: uuid.UUID) -> bool:
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                status=ConversationStatusEnum.CLOSED,
                closed_at=datetime.now(timezone.utc),
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def list_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        channel: Optional[ChannelEnum] = None,
        status: Optional[ConversationStatusEnum] = None,
    ) -> Tuple[List[Conversation], int]:
        """Retorna conversas paginadas com contagem total."""
        filters = []
        if channel:
            filters.append(Conversation.channel == channel)
        if status:
            filters.append(Conversation.status == status)

        # Count
        count_stmt = select(func.count()).select_from(Conversation)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total = (await self.db.execute(count_stmt)).scalar_one()

        # Data
        stmt = (
            select(Conversation)
            .order_by(Conversation.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if filters:
            stmt = stmt.where(and_(*filters))

        result = await self.db.execute(stmt)
        return result.scalars().all(), total

    async def count_total(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Conversation))
        return result.scalar_one()

    async def count_active(self) -> int:
        stmt = select(func.count()).select_from(Conversation).where(
            Conversation.status == ConversationStatusEnum.ACTIVE
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()


# ──────────────────────────────────────────────────────────────────────────────
# MessageRepository
# ──────────────────────────────────────────────────────────────────────────────
class MessageRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        conversation_id: uuid.UUID,
        role: MessageRoleEnum,
        content: str,
        status: MessageStatusEnum = MessageStatusEnum.RECEIVED,
        external_message_id: Optional[str] = None,
        tokens_used: Optional[int] = None,
        model_used: Optional[str] = None,
        latency_ms: Optional[float] = None,
        channel_metadata: Optional[dict] = None,
        ai_metadata: Optional[dict] = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            status=status,
            external_message_id=external_message_id,
            tokens_used=tokens_used,
            model_used=model_used,
            latency_ms=latency_ms,
            channel_metadata=channel_metadata or {},
            ai_metadata=ai_metadata or {},
        )
        self.db.add(message)
        await self.db.flush()
        return message

    async def update_status(
        self,
        message_id: uuid.UUID,
        status: MessageStatusEnum,
        error_message: Optional[str] = None,
    ) -> None:
        values: Dict = {"status": status}
        if error_message:
            values["error_message"] = error_message

        stmt = update(Message).where(Message.id == message_id).values(**values)
        await self.db.execute(stmt)

    async def count_total(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Message))
        return result.scalar_one()

    async def count_today(self) -> int:
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.count()).select_from(Message).where(
            Message.created_at >= today
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def avg_response_time(self) -> Optional[float]:
        """Tempo médio de resposta da IA em ms."""
        stmt = select(func.avg(Message.latency_ms)).where(
            and_(
                Message.role == MessageRoleEnum.ASSISTANT,
                Message.latency_ms.is_not(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def count_by_channel(self) -> Dict[str, int]:
        stmt = (
            select(Conversation.channel, func.count(Message.id))
            .join(Message.conversation)
            .group_by(Conversation.channel)
        )
        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.fetchall()}


# ──────────────────────────────────────────────────────────────────────────────
# AuditLogRepository
# ──────────────────────────────────────────────────────────────────────────────
class AuditLogRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: Optional[str] = "system",
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        audit = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            details=details,
            ip_address=ip_address,
        )
        self.db.add(audit)
        await self.db.flush()
        return audit
