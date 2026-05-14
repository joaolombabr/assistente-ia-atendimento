"""
Configurações centralizadas da aplicação usando Pydantic Settings.
Todas as variáveis de ambiente são validadas e tipadas aqui.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configurações da aplicação carregadas do .env.
    O decorador @lru_cache garante que o objeto seja criado apenas uma vez.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Assistente IA para Atendimento"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")
    DEBUG: bool = False
    SHOW_DOCS: bool = True
    SECRET_KEY: str = Field(..., min_length=32)

    # ── Server ───────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    ALLOWED_HOSTS: List[str] = ["*"]
    CORS_ORIGINS: List[str] = ["*"]

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/atendimento"
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # ── Redis (cache + filas) ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600  # 1 hora
    REDIS_QUEUE_NAME: str = "ai_messages"

    # ── OpenAI ───────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(...)
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 1000
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_TIMEOUT: int = 30
    OPENAI_MAX_RETRIES: int = 3
    OPENAI_CONTEXT_WINDOW: int = 20  # Número de mensagens anteriores no contexto

    # ── System Prompt ─────────────────────────────────────────────────────────
    AI_SYSTEM_PROMPT: str = (
        "Você é um assistente de atendimento profissional e prestativo. "
        "Responda de forma clara, objetiva e amigável. "
        "Se não souber a resposta, diga educadamente que irá verificar. "
        "Mantenha um tom profissional mas humano."
    )

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    WHATSAPP_API_URL: str = "https://graph.facebook.com/v18.0"
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""  # Token de verificação do webhook

    # ── Telegram ──────────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_API_URL: str = "https://api.telegram.org"

    # ── Auth ──────────────────────────────────────────────────────────────────
    API_KEY_HEADER: str = "X-API-Key"
    INTERNAL_API_KEY: str = Field(...)  # Chave para comunicação interna (ex: n8n)
    JWT_SECRET_KEY: str = Field(...)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # segundos

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" ou "console"

    # ── n8n ───────────────────────────────────────────────────────────────────
    N8N_WEBHOOK_URL: Optional[str] = None
    N8N_API_KEY: Optional[str] = None

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Garante que a URL do banco usa asyncpg para operações assíncronas."""
        if v.startswith("postgresql://") and "asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://")
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache()
def get_settings() -> Settings:
    """
    Retorna instância singleton das configurações.
    O @lru_cache evita recriar o objeto a cada chamada.
    """
    return Settings()
