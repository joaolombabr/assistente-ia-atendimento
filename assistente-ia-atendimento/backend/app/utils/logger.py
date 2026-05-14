"""
Configuração de logging estruturado com structlog.
Suporta saída em JSON (produção) e console colorido (desenvolvimento).
"""

import logging
import sys

import structlog

from app.config.settings import get_settings

settings = get_settings()


def setup_logging() -> None:
    """
    Configura o sistema de logging estruturado.
    
    Em desenvolvimento: logs coloridos e legíveis no console.
    Em produção: logs em JSON para ingestão por ferramentas (Datadog, ELK, etc.)
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Configura logging padrão do Python
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Silencia loggers muito verbosos
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Escolhe o renderer baseado no ambiente
    if settings.LOG_FORMAT == "json" or settings.is_production:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            # Adiciona timestamp ISO 8601
            structlog.processors.TimeStamper(fmt="iso"),
            # Adiciona nível de log
            structlog.stdlib.add_log_level,
            # Adiciona nome do logger
            structlog.stdlib.add_logger_name,
            # Suporte a exc_info=True
            structlog.processors.ExceptionRenderer(),
            # Adiciona contextvars (request_id, etc.)
            structlog.contextvars.merge_contextvars,
            # Stack info para erros
            structlog.processors.StackInfoRenderer(),
            # Renderer final
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
