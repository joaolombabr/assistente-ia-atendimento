"""
Router de Health Check — verifica status dos serviços.
"""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config.settings import get_settings
from app.database.connection import get_db
from app.schemas.schemas import HealthResponse

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter()


@router.get("", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Verifica saúde de todos os serviços dependentes."""
    services = {}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        services["database"] = "healthy"
    except Exception as e:
        services["database"] = f"unhealthy: {str(e)[:50]}"

    # Redis
    try:
        from app.workers.queue import get_redis
        redis = await get_redis()
        await redis.ping()
        services["redis"] = "healthy"
    except Exception as e:
        services["redis"] = f"unhealthy: {str(e)[:50]}"

    # OpenAI (apenas verifica se a chave está configurada)
    services["openai"] = "configured" if settings.OPENAI_API_KEY else "not_configured"

    overall = "healthy" if all("unhealthy" not in v for v in services.values()) else "degraded"

    return HealthResponse(
        status=overall,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        services=services,
    )


@router.get("/live")
async def liveness() -> dict:
    """Liveness probe para Kubernetes/Docker."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness probe — verifica se pode receber tráfego."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        from fastapi import Response
        return Response(status_code=503, content='{"status": "not_ready"}')
