"""
Integração com OpenAI API.
Gerencia chamadas, contexto de conversa, retry automático e métricas.
"""

import time
from typing import Dict, List, Optional

import structlog
from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.config.settings import get_settings
from app.schemas.schemas import AIRequest, AIResponse

logger = structlog.get_logger(__name__)
settings = get_settings()


class OpenAIService:
    """
    Serviço de integração com a OpenAI API.
    
    Funcionalidades:
    - Chat completion com contexto de conversa
    - Retry automático com backoff exponencial
    - Métricas de latência e uso de tokens
    - Suporte a múltiplos modelos
    - System prompt configurável por conversa
    """

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        """Lazy initialization do client OpenAI."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=settings.OPENAI_TIMEOUT,
                max_retries=0,  # Gerenciamos retry manualmente com tenacity
            )
        return self._client

    def build_messages(
        self,
        user_message: str,
        context_messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Constrói a lista de mensagens para a API da OpenAI.
        
        Estrutura:
        [system] → [histórico de contexto] → [nova mensagem do usuário]
        """
        messages = []

        # System prompt (configurável por conversa ou usa o padrão)
        effective_system_prompt = system_prompt or settings.AI_SYSTEM_PROMPT
        messages.append({"role": "system", "content": effective_system_prompt})

        # Histórico de contexto (limitado para não exceder token window)
        # Garante que alternamos entre user/assistant corretamente
        for msg in context_messages[-settings.OPENAI_CONTEXT_WINDOW:]:
            if msg.get("role") in ("user", "assistant") and msg.get("content"):
                messages.append({"role": msg["role"], "content": msg["content"]})

        # Nova mensagem do usuário
        messages.append({"role": "user", "content": user_message})

        return messages

    @retry(
        retry=retry_if_exception_type((APITimeoutError, RateLimitError)),
        stop=stop_after_attempt(settings.OPENAI_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        before_sleep=before_sleep_log(logger, "warning"),
    )
    async def _call_api(
        self, messages: List[Dict[str, str]], model: str
    ) -> dict:
        """
        Chama a API da OpenAI com retry automático.
        Retry apenas em timeout e rate limit (não em erros de autenticação).
        """
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=settings.OPENAI_TEMPERATURE,
        )
        return response

    async def generate_response(self, request: AIRequest) -> AIResponse:
        """
        Gera resposta da IA para uma mensagem do usuário.
        
        Args:
            request: AIRequest com mensagem, contexto e prompt opcional
            
        Returns:
            AIResponse com conteúdo, métricas e metadados
        """
        start_time = time.perf_counter()

        messages = self.build_messages(
            user_message=request.user_message,
            context_messages=request.context_messages,
            system_prompt=request.system_prompt,
        )

        log = logger.bind(
            conversation_id=str(request.conversation_id),
            model=settings.OPENAI_MODEL,
            context_size=len(request.context_messages),
        )

        log.info("ai.request_start")

        try:
            response = await self._call_api(
                messages=messages,
                model=settings.OPENAI_MODEL,
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0
            finish_reason = response.choices[0].finish_reason or "stop"

            log.info(
                "ai.request_complete",
                latency_ms=round(latency_ms, 2),
                tokens_used=tokens_used,
                finish_reason=finish_reason,
            )

            return AIResponse(
                content=content,
                model=settings.OPENAI_MODEL,
                tokens_used=tokens_used,
                finish_reason=finish_reason,
                latency_ms=round(latency_ms, 2),
            )

        except RateLimitError as e:
            log.error("ai.rate_limit_exceeded", error=str(e))
            raise

        except APITimeoutError as e:
            log.error("ai.timeout", error=str(e))
            raise

        except APIError as e:
            log.error("ai.api_error", error=str(e), status_code=e.status_code)
            raise

    async def generate_conversation_title(self, first_message: str) -> str:
        """Gera um título curto para a conversa baseado na primeira mensagem."""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Gere um título curto (máx 50 chars) para esta conversa de atendimento. Responda APENAS com o título, sem aspas.",
                    },
                    {"role": "user", "content": first_message},
                ],
                max_tokens=30,
                temperature=0.5,
            )
            return response.choices[0].message.content or "Nova conversa"
        except Exception:
            return "Nova conversa"


# Singleton — reutilizado em toda a aplicação
openai_service = OpenAIService()
