"""
Schemas Pydantic v2 para validação de entrada/saída da API.
Separados por domínio: Webhook, Conversation, Message, User.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.models import ChannelEnum, ConversationStatusEnum, MessageRoleEnum, MessageStatusEnum


# ──────────────────────────────────────────────────────────────────────────────
# Base schemas reutilizáveis
# ──────────────────────────────────────────────────────────────────────────────
class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# ──────────────────────────────────────────────────────────────────────────────
# Webhook — WhatsApp
# ──────────────────────────────────────────────────────────────────────────────
class WhatsAppContact(BaseModel):
    wa_id: str
    profile: Optional[Dict[str, Any]] = None


class WhatsAppTextMessage(BaseModel):
    body: str


class WhatsAppMessage(BaseModel):
    id: str
    from_: str = Field(..., alias="from")
    timestamp: str
    type: str
    text: Optional[WhatsAppTextMessage] = None

    model_config = ConfigDict(populate_by_name=True)


class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: Dict[str, Any]
    contacts: Optional[List[WhatsAppContact]] = None
    messages: Optional[List[WhatsAppMessage]] = None
    statuses: Optional[List[Dict[str, Any]]] = None


class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str


class WhatsAppEntry(BaseModel):
    id: str
    changes: List[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    """Payload completo de um webhook do WhatsApp Business API."""
    object: str
    entry: List[WhatsAppEntry]


# ──────────────────────────────────────────────────────────────────────────────
# Webhook — Telegram
# ──────────────────────────────────────────────────────────────────────────────
class TelegramUser(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None


class TelegramChat(BaseModel):
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None


class TelegramMessage(BaseModel):
    message_id: int
    from_: Optional[TelegramUser] = Field(None, alias="from")
    chat: TelegramChat
    date: int
    text: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class TelegramWebhookPayload(BaseModel):
    """Payload de um update do Telegram Bot API."""
    update_id: int
    message: Optional[TelegramMessage] = None
    edited_message: Optional[TelegramMessage] = None


# ──────────────────────────────────────────────────────────────────────────────
# Webhook — Resposta da API após processar
# ──────────────────────────────────────────────────────────────────────────────
class WebhookProcessedResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    queued: bool = False
    detail: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Mensagem normalizada (agnóstica de canal)
# ──────────────────────────────────────────────────────────────────────────────
class IncomingMessage(BaseModel):
    """
    Representação interna de uma mensagem recebida.
    Criada após normalizar payloads de WhatsApp ou Telegram.
    """
    external_id: str           # ID da mensagem no canal
    user_external_id: str      # ID do usuário no canal
    channel: ChannelEnum
    content: str
    user_name: Optional[str] = None
    user_phone: Optional[str] = None
    user_username: Optional[str] = None
    raw_payload: Dict[str, Any] = {}


# ──────────────────────────────────────────────────────────────────────────────
# User schemas
# ──────────────────────────────────────────────────────────────────────────────
class UserOut(BaseSchema):
    id: uuid.UUID
    external_id: str
    channel: str
    name: Optional[str]
    phone_number: Optional[str]
    username: Optional[str]
    language_code: str
    is_active: bool
    is_blocked: bool
    created_at: datetime
    updated_at: datetime


# ──────────────────────────────────────────────────────────────────────────────
# Message schemas
# ──────────────────────────────────────────────────────────────────────────────
class MessageOut(BaseSchema):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    status: str
    tokens_used: Optional[int]
    model_used: Optional[str]
    latency_ms: Optional[float]
    created_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4096)
    role: MessageRoleEnum = MessageRoleEnum.USER


# ──────────────────────────────────────────────────────────────────────────────
# Conversation schemas
# ──────────────────────────────────────────────────────────────────────────────
class ConversationOut(BaseSchema):
    id: uuid.UUID
    user_id: uuid.UUID
    channel: str
    status: str
    title: Optional[str]
    tags: Optional[List[str]]
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationWithMessages(ConversationOut):
    messages: List[MessageOut] = []
    user: Optional[UserOut] = None


class ConversationListResponse(BaseModel):
    items: List[ConversationOut]
    total: int
    page: int
    page_size: int
    pages: int


# ──────────────────────────────────────────────────────────────────────────────
# AI Request/Response
# ──────────────────────────────────────────────────────────────────────────────
class AIRequest(BaseModel):
    """Requisição para o serviço de IA."""
    conversation_id: uuid.UUID
    user_message: str
    system_prompt: Optional[str] = None
    context_messages: List[Dict[str, str]] = []


class AIResponse(BaseModel):
    """Resposta do serviço de IA."""
    content: str
    model: str
    tokens_used: int
    finish_reason: str
    latency_ms: float


# ──────────────────────────────────────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    services: Dict[str, str]


# ──────────────────────────────────────────────────────────────────────────────
# Admin / Stats
# ──────────────────────────────────────────────────────────────────────────────
class StatsResponse(BaseModel):
    total_users: int
    total_conversations: int
    total_messages: int
    active_conversations: int
    messages_today: int
    avg_response_time_ms: Optional[float]
    channels: Dict[str, int]


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
