"""
Router de Webhooks — recebe mensagens do WhatsApp e Telegram.
Normaliza os payloads e enfileira para processamento assíncrono.
"""

import hashlib
import hmac
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.database.connection import get_db
from app.models.models import ChannelEnum
from app.schemas.schemas import (
    IncomingMessage,
    TelegramWebhookPayload,
    WebhookProcessedResponse,
    WhatsAppWebhookPayload,
)
from app.services.conversation_service import ConversationService
from app.workers.queue import enqueue_message

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()


# ──────────────────────────────────────────────────────────────────────────────
# WhatsApp Webhooks
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/whatsapp", response_class=PlainTextResponse, include_in_schema=True)
async def whatsapp_verify(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> str:
    """
    Endpoint de verificação do webhook WhatsApp.
    Meta chama este endpoint para confirmar que você controla o servidor.
    
    Configure o mesmo WHATSAPP_VERIFY_TOKEN no painel Meta e no .env.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("whatsapp.webhook_verified")
        return hub_challenge

    logger.warning("whatsapp.webhook_verification_failed", token_received=hub_verify_token[:10])
    raise HTTPException(status_code=403, detail="Verificação do webhook falhou")


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    payload: WhatsAppWebhookPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> WebhookProcessedResponse:
    """
    Recebe eventos do WhatsApp Business API.
    
    Processa:
    - Mensagens de texto recebidas
    - Status de entrega (ignorados aqui, podem ser logados)
    
    Retorna 200 rapidamente e processa em background (obrigatório pelo WhatsApp).
    """
    # Verifica assinatura da Meta (segurança)
    await _verify_whatsapp_signature(request)

    # Processa apenas mensagens (ignora status updates)
    for entry in payload.entry:
        for change in entry.changes:
            if change.field != "messages":
                continue

            value = change.value
            if not value.messages:
                continue

            for wpp_msg in value.messages:
                # Ignora mensagens não-texto (áudio, imagem, etc.) por ora
                if wpp_msg.type != "text" or not wpp_msg.text:
                    logger.info("whatsapp.unsupported_message_type", msg_type=wpp_msg.type)
                    continue

                # Encontra o nome do contato
                contact_name = None
                if value.contacts:
                    contact = next(
                        (c for c in value.contacts if c.wa_id == wpp_msg.from_),
                        None,
                    )
                    if contact and contact.profile:
                        contact_name = contact.profile.get("name")

                incoming = IncomingMessage(
                    external_id=wpp_msg.id,
                    user_external_id=wpp_msg.from_,
                    channel=ChannelEnum.WHATSAPP,
                    content=wpp_msg.text.body,
                    user_name=contact_name,
                    user_phone=wpp_msg.from_,
                    raw_payload=payload.model_dump(),
                )

                logger.info(
                    "whatsapp.message_received",
                    from_number=wpp_msg.from_[:5] + "***",
                    message_id=wpp_msg.id,
                    content_preview=wpp_msg.text.body[:50],
                )

                # Enfileira para processamento assíncrono
                # WhatsApp exige resposta em < 5s, então processamos em background
                background_tasks.add_task(
                    _process_message_background, incoming, db
                )

                return WebhookProcessedResponse(
                    success=True,
                    queued=True,
                    detail="Mensagem recebida e em processamento",
                )

    return WebhookProcessedResponse(success=True, detail="Nenhuma mensagem para processar")


# ──────────────────────────────────────────────────────────────────────────────
# Telegram Webhooks
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/telegram")
async def telegram_webhook(
    payload: TelegramWebhookPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> WebhookProcessedResponse:
    """
    Recebe updates do Telegram Bot API.
    
    Processa mensagens de texto. Outros tipos (fotos, stickers, etc.)
    podem ser adicionados conforme necessidade.
    """
    # Usa message ou edited_message
    tg_message = payload.message or payload.edited_message
    if not tg_message:
        return WebhookProcessedResponse(success=True, detail="Sem mensagem no payload")

    if not tg_message.text:
        logger.info("telegram.non_text_message", update_id=payload.update_id)
        return WebhookProcessedResponse(success=True, detail="Mensagem não-texto ignorada")

    sender = tg_message.from_
    if not sender:
        return WebhookProcessedResponse(success=True, detail="Mensagem sem remetente")

    # Monta nome completo
    user_name = sender.first_name
    if sender.last_name:
        user_name += f" {sender.last_name}"

    incoming = IncomingMessage(
        external_id=str(tg_message.message_id),
        user_external_id=str(sender.id),
        channel=ChannelEnum.TELEGRAM,
        content=tg_message.text,
        user_name=user_name,
        user_username=sender.username,
        raw_payload=payload.model_dump(),
    )

    logger.info(
        "telegram.message_received",
        user_id=sender.id,
        username=sender.username,
        content_preview=tg_message.text[:50],
        update_id=payload.update_id,
    )

    background_tasks.add_task(_process_message_background, incoming, db)

    return WebhookProcessedResponse(
        success=True,
        queued=True,
        detail="Mensagem recebida e em processamento",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Funções auxiliares
# ──────────────────────────────────────────────────────────────────────────────
async def _process_message_background(incoming: IncomingMessage, db: AsyncSession) -> None:
    """
    Processa a mensagem em background task.
    Cria nova sessão de DB para o contexto assíncrono.
    """
    from app.database.connection import get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            service = ConversationService(session)
            await service.process_message(incoming)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(
                "background.processing_failed",
                channel=incoming.channel,
                error=str(e),
                exc_info=True,
            )


async def _verify_whatsapp_signature(request: Request) -> None:
    """
    Verifica a assinatura X-Hub-Signature-256 do WhatsApp.
    Garante que a requisição veio da Meta e não de terceiros.
    """
    # Em desenvolvimento, pula verificação se não configurado
    if settings.is_development:
        return

    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header:
        raise HTTPException(status_code=401, detail="Assinatura ausente")

    body = await request.body()
    expected_signature = hmac.new(
        settings.SECRET_KEY.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    expected = f"sha256={expected_signature}"
    if not hmac.compare_digest(signature_header, expected):
        raise HTTPException(status_code=401, detail="Assinatura inválida")
