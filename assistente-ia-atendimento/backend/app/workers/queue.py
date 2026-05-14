"""
Fila assíncrona usando Redis para processamento de mensagens.
Desacopla o recebimento do webhook do processamento pela IA.
"""

from typing import Optional

import redis.asyncio as aioredis
import structlog

from app.config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Retorna instância singleton do Redis."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def init_queue() -> None:
    """Inicializa a conexão com Redis."""
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("queue.redis_connected", url=settings.REDIS_URL)
    except Exception as e:
        logger.warning("queue.redis_unavailable", error=str(e))
        # Não falha o startup — Redis é opcional para funcionalidade básica


async def close_queue() -> None:
    """Fecha a conexão com Redis."""
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        logger.info("queue.redis_disconnected")


async def enqueue_message(message_data: dict) -> bool:
    """
    Adiciona mensagem na fila Redis para processamento assíncrono.
    Útil quando queremos desacoplar completamente o webhook do processamento.
    
    Returns:
        True se enfileirado, False se falhou (fallback para processamento síncrono)
    """
    import json

    try:
        redis = await get_redis()
        await redis.rpush(settings.REDIS_QUEUE_NAME, json.dumps(message_data))
        logger.info("queue.message_enqueued", queue=settings.REDIS_QUEUE_NAME)
        return True
    except Exception as e:
        logger.warning("queue.enqueue_failed", error=str(e))
        return False


async def cache_set(key: str, value: str, ttl: int = None) -> None:
    """Salva valor no cache Redis."""
    try:
        redis = await get_redis()
        effective_ttl = ttl or settings.REDIS_CACHE_TTL
        await redis.setex(key, effective_ttl, value)
    except Exception as e:
        logger.warning("cache.set_failed", key=key, error=str(e))


async def cache_get(key: str) -> Optional[str]:
    """Recupera valor do cache Redis."""
    try:
        redis = await get_redis()
        return await redis.get(key)
    except Exception as e:
        logger.warning("cache.get_failed", key=key, error=str(e))
        return None


async def cache_delete(key: str) -> None:
    """Remove valor do cache."""
    try:
        redis = await get_redis()
        await redis.delete(key)
    except Exception:
        pass
