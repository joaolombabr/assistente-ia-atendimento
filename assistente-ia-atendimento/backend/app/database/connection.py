"""
Gerenciamento de conexão com o banco de dados PostgreSQL.
Usa SQLAlchemy 2.0 com suporte assíncrono via asyncpg.
"""

from typing import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# ──────────────────────────────────────────────────────────────────────────────
# Base declarativa para todos os models
# ──────────────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Base para todos os models SQLAlchemy."""
    pass


# ──────────────────────────────────────────────────────────────────────────────
# Engine assíncrono — singleton
# ──────────────────────────────────────────────────────────────────────────────
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DATABASE_ECHO,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_pre_ping=True,  # Verifica conexão antes de usar
            pool_recycle=3600,   # Recicla conexões a cada 1h
        )
    return _engine


def get_session_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,  # Evita re-fetch após commit
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


# ──────────────────────────────────────────────────────────────────────────────
# Lifecycle
# ──────────────────────────────────────────────────────────────────────────────
async def init_db() -> None:
    """
    Inicializa o banco de dados.
    Em produção, use Alembic para migrations — não crie tabelas aqui.
    Aqui fazemos apenas verificação de conectividade.
    """
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        logger.info("database.connected", url=settings.DATABASE_URL.split("@")[-1])
    except Exception as e:
        logger.error("database.connection_failed", error=str(e))
        raise


async def close_db() -> None:
    """Fecha todas as conexões do pool."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("database.disconnected")


# ──────────────────────────────────────────────────────────────────────────────
# Dependency para injeção nas rotas FastAPI
# ──────────────────────────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency do FastAPI que fornece uma sessão de banco por requisição.
    Garante rollback em caso de erro e fechamento da sessão ao final.

    Uso:
        @router.get("/exemplo")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
