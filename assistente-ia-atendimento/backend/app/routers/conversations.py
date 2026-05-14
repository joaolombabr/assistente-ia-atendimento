"""
Router de Conversas — CRUD completo com paginação e filtros.
"""

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.models.models import ChannelEnum, ConversationStatusEnum
from app.repositories.repositories import ConversationRepository
from app.schemas.schemas import ConversationListResponse, ConversationWithMessages

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    channel: Optional[ChannelEnum] = None,
    status: Optional[ConversationStatusEnum] = None,
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """Lista conversas com paginação e filtros opcionais."""
    repo = ConversationRepository(db)
    items, total = await repo.list_paginated(
        page=page, page_size=page_size, channel=channel, status=status
    )
    import math
    return ConversationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ConversationWithMessages:
    """Retorna uma conversa com todo o histórico de mensagens."""
    repo = ConversationRepository(db)
    conversation = await repo.get_with_messages(conversation_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    return conversation


@router.patch("/{conversation_id}/close")
async def close_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Encerra uma conversa ativa."""
    repo = ConversationRepository(db)
    success = await repo.close_conversation(conversation_id)

    if not success:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    logger.info("conversation.closed_via_api", conversation_id=str(conversation_id))
    return {"success": True, "message": "Conversa encerrada"}
