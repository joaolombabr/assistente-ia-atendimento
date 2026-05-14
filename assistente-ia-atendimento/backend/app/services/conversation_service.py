"""
Serviço principal de orquestração do fluxo de atendimento.
Coordena: normalização → banco → IA → resposta no canal.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.messaging import whatsapp_service, telegram_service
from app.integrations.openai_service import openai_service
from app.models.models import ChannelEnum, MessageRoleEnum, MessageStatusEnum
from app.repositories.repositories import (
    ConversationRepository,
    MessageRepository,
    UserRepository,
)
from app.schemas.schemas import AIRequest, IncomingMessage

logger = structlog.get_logger(__name__)


class ConversationService:
    """
    Orquestra o fluxo completo de uma mensagem recebida:
    1. Upsert do usuário
    2. Busca/cria conversa ativa
    3. Salva mensagem do usuário
    4. Busca contexto da conversa
    5. Chama OpenAI
    6. Salva resposta da IA
    7. Envia resposta no canal correto
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.conv_repo = ConversationRepository(db)
        self.msg_repo = MessageRepository(db)

    async def process_message(self, incoming: IncomingMessage) -> dict:
        """
        Processa uma mensagem recebida do início ao fim.
        
        Returns:
            Dict com IDs gerados e status da operação
        """
        log = logger.bind(
            channel=incoming.channel,
            user_external_id=incoming.user_external_id,
        )
        log.info("conversation.processing_start")

        # ── 1. Upsert do usuário ─────────────────────────────────────────────
        user, user_created = await self.user_repo.get_or_create(
            external_id=incoming.user_external_id,
            channel=incoming.channel,
            name=incoming.user_name,
            phone_number=incoming.user_phone,
            username=incoming.user_username,
        )

        if user.is_blocked:
            log.warning("conversation.user_blocked", user_id=str(user.id))
            return {"status": "blocked", "user_id": str(user.id)}

        # ── 2. Conversa ativa ────────────────────────────────────────────────
        conversation, conv_created = await self.conv_repo.get_active_or_create(
            user_id=user.id,
            channel=incoming.channel,
        )

        # ── 3. Salva mensagem do usuário ─────────────────────────────────────
        user_message = await self.msg_repo.create(
            conversation_id=conversation.id,
            role=MessageRoleEnum.USER,
            content=incoming.content,
            status=MessageStatusEnum.RECEIVED,
            external_message_id=incoming.external_id,
            channel_metadata=incoming.raw_payload,
        )
        await self.conv_repo.increment_message_count(conversation.id)

        # ── 4. Indicador de digitação (melhora UX) ────────────────────────────
        await self._send_typing_indicator(incoming)

        # ── 5. Busca contexto ────────────────────────────────────────────────
        recent_messages = await self.conv_repo.get_recent_messages(
            conversation.id, limit=20
        )
        context = [
            {"role": msg.role, "content": msg.content}
            for msg in recent_messages
            if msg.id != user_message.id  # Exclui a mensagem que acabamos de salvar
        ]

        # ── 6. Gera resposta com IA ───────────────────────────────────────────
        try:
            ai_response = await openai_service.generate_response(
                AIRequest(
                    conversation_id=conversation.id,
                    user_message=incoming.content,
                    system_prompt=conversation.system_prompt,
                    context_messages=context,
                )
            )

            # ── 7. Salva resposta da IA ──────────────────────────────────────
            ai_message = await self.msg_repo.create(
                conversation_id=conversation.id,
                role=MessageRoleEnum.ASSISTANT,
                content=ai_response.content,
                status=MessageStatusEnum.SENT,
                tokens_used=ai_response.tokens_used,
                model_used=ai_response.model,
                latency_ms=ai_response.latency_ms,
                ai_metadata={
                    "finish_reason": ai_response.finish_reason,
                    "model": ai_response.model,
                },
            )
            await self.conv_repo.increment_message_count(conversation.id)

            # ── 8. Gera título da conversa (apenas na 1ª mensagem) ────────────
            if conv_created:
                title = await openai_service.generate_conversation_title(incoming.content)
                from sqlalchemy import update
                from app.models.models import Conversation
                await self.db.execute(
                    update(Conversation)
                    .where(Conversation.id == conversation.id)
                    .values(title=title)
                )

            # ── 9. Envia resposta no canal ────────────────────────────────────
            await self._send_response(incoming, ai_response.content)

            log.info(
                "conversation.processing_complete",
                conversation_id=str(conversation.id),
                user_message_id=str(user_message.id),
                ai_message_id=str(ai_message.id),
                latency_ms=ai_response.latency_ms,
            )

            return {
                "status": "success",
                "user_id": str(user.id),
                "conversation_id": str(conversation.id),
                "user_message_id": str(user_message.id),
                "ai_message_id": str(ai_message.id),
                "tokens_used": ai_response.tokens_used,
            }

        except Exception as e:
            # Atualiza o status da mensagem do usuário como falho
            await self.msg_repo.update_status(
                message_id=user_message.id,
                status=MessageStatusEnum.FAILED,
                error_message=str(e),
            )
            log.error("conversation.processing_failed", error=str(e), exc_info=True)
            raise

    async def _send_typing_indicator(self, incoming: IncomingMessage) -> None:
        """Envia indicador de digitação no canal correspondente."""
        try:
            if incoming.channel == ChannelEnum.TELEGRAM:
                chat_id = int(incoming.user_external_id)
                await telegram_service.send_chat_action(chat_id, "typing")
            # WhatsApp não tem suporte nativo a "digitando" via Cloud API
        except Exception:
            pass  # Não é crítico

    async def _send_response(self, incoming: IncomingMessage, response_text: str) -> None:
        """Envia a resposta no canal de origem da mensagem."""
        if incoming.channel == ChannelEnum.WHATSAPP:
            await whatsapp_service.send_text_message(
                to=incoming.user_external_id,
                message=response_text,
            )
            # Marca mensagem original como lida
            if incoming.external_id:
                await whatsapp_service.mark_as_read(incoming.external_id)

        elif incoming.channel == ChannelEnum.TELEGRAM:
            await telegram_service.send_message(
                chat_id=int(incoming.user_external_id),
                text=response_text,
            )
