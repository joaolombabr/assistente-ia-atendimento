"""
Integrações com WhatsApp Business API e Telegram Bot API.
Cada serviço é responsável por enviar mensagens no respectivo canal.
"""

from typing import Optional

import httpx
import structlog

from app.config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


# ──────────────────────────────────────────────────────────────────────────────
# WhatsApp Service
# ──────────────────────────────────────────────────────────────────────────────
class WhatsAppService:
    """
    Serviço para envio de mensagens via WhatsApp Business API (Meta Graph API).
    
    Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/messages
    """

    def __init__(self):
        self.base_url = settings.WHATSAPP_API_URL
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN

    async def send_text_message(
        self, to: str, message: str, preview_url: bool = False
    ) -> dict:
        """
        Envia mensagem de texto para um número WhatsApp.
        
        Args:
            to: Número no formato internacional sem + (ex: 5511999999999)
            message: Texto da mensagem
        """
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": message,
            },
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

                logger.info(
                    "whatsapp.message_sent",
                    to=to[:5] + "***",  # Mascara o número nos logs
                    message_id=data.get("messages", [{}])[0].get("id"),
                )
                return data

            except httpx.HTTPStatusError as e:
                logger.error(
                    "whatsapp.send_failed",
                    status_code=e.response.status_code,
                    response_body=e.response.text,
                )
                raise
            except httpx.TimeoutException:
                logger.error("whatsapp.send_timeout", to=to[:5] + "***")
                raise

    async def mark_as_read(self, message_id: str) -> None:
        """Marca uma mensagem como lida (ativa os dois checks azuis)."""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                await client.post(url, json=payload, headers=headers)
            except Exception as e:
                # Falha ao marcar como lido não é crítica
                logger.warning("whatsapp.mark_read_failed", error=str(e))

    async def send_typing_indicator(self, to: str) -> None:
        """
        Envia indicador de digitação.
        Melhora a experiência do usuário enquanto a IA processa.
        """
        # WhatsApp Cloud API não suporta "typing" diretamente
        # Pode ser simulado via status de presença em algumas implementações
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Telegram Service
# ──────────────────────────────────────────────────────────────────────────────
class TelegramService:
    """
    Serviço para envio de mensagens via Telegram Bot API.
    
    Docs: https://core.telegram.org/bots/api
    """

    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"{settings.TELEGRAM_API_URL}/bot{self.token}"

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str = "HTML",
        reply_to_message_id: Optional[int] = None,
        disable_notification: bool = False,
    ) -> dict:
        """
        Envia mensagem de texto para um chat do Telegram.
        
        Args:
            chat_id: ID do chat ou @username
            text: Texto da mensagem (suporta HTML e Markdown)
            parse_mode: "HTML" ou "MarkdownV2"
        """
        url = f"{self.base_url}/sendMessage"
        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
        }
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                if not data.get("ok"):
                    raise ValueError(f"Telegram API error: {data.get('description')}")

                logger.info(
                    "telegram.message_sent",
                    chat_id=str(chat_id),
                    message_id=data["result"]["message_id"],
                )
                return data["result"]

            except httpx.HTTPStatusError as e:
                logger.error(
                    "telegram.send_failed",
                    status_code=e.response.status_code,
                    response_body=e.response.text,
                )
                raise

    async def send_chat_action(self, chat_id: int | str, action: str = "typing") -> None:
        """
        Envia indicador de ação (ex: "digitando...").
        Deve ser chamado antes de processar a resposta para feedback visual.
        """
        url = f"{self.base_url}/sendChatAction"
        payload = {"chat_id": chat_id, "action": action}

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                await client.post(url, json=payload)
            except Exception as e:
                logger.warning("telegram.chat_action_failed", error=str(e))

    async def set_webhook(self, webhook_url: str, secret_token: Optional[str] = None) -> dict:
        """Configura o webhook do bot Telegram."""
        url = f"{self.base_url}/setWebhook"
        payload: dict = {"url": webhook_url}
        if secret_token:
            payload["secret_token"] = secret_token

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            return response.json()

    async def get_webhook_info(self) -> dict:
        """Retorna informações sobre o webhook configurado."""
        url = f"{self.base_url}/getWebhookInfo"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            return response.json()


# Singletons
whatsapp_service = WhatsAppService()
telegram_service = TelegramService()
