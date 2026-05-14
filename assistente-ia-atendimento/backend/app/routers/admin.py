"""
Router Admin — estatísticas e operações administrativas.
Requer autenticação especial (admin key).
"""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.repositories.repositories import (
    ConversationRepository,
    MessageRepository,
    UserRepository,
)
from app.schemas.schemas import StatsResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)) -> StatsResponse:
    """Retorna estatísticas gerais do sistema."""
    user_repo = UserRepository(db)
    conv_repo = ConversationRepository(db)
    msg_repo = MessageRepository(db)

    total_users = await user_repo.count_total()
    total_conversations = await conv_repo.count_total()
    total_messages = await msg_repo.count_total()
    active_conversations = await conv_repo.count_active()
    messages_today = await msg_repo.count_today()
    avg_response_time = await msg_repo.avg_response_time()
    channels = await msg_repo.count_by_channel()

    return StatsResponse(
        total_users=total_users,
        total_conversations=total_conversations,
        total_messages=total_messages,
        active_conversations=active_conversations,
        messages_today=messages_today,
        avg_response_time_ms=avg_response_time,
        channels=channels,
    )
