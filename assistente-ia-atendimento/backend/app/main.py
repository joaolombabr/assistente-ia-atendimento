"""
Assistente IA para Atendimento - Main Application
Ponto de entrada da API FastAPI com configuração completa de middleware,
routers, eventos de lifecycle e documentação.
"""

import logging
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.database.connection import init_db, close_db
from app.middleware.auth import AuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import health, webhooks, conversations, admin
from app.utils.logger import setup_logging
from app.workers.queue import init_queue, close_queue

# ──────────────────────────────────────────────────────────────────────────────
# Bootstrap de logging estruturado (deve ocorrer antes de qualquer import)
# ──────────────────────────────────────────────────────────────────────────────
setup_logging()
logger = structlog.get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    Executa inicializações no startup e limpeza no shutdown.
    """
    # ── STARTUP ──────────────────────────────────────────────────────────────
    logger.info("startup.begin", environment=settings.ENVIRONMENT, version=settings.APP_VERSION)

    await init_db()
    logger.info("startup.database_ready")

    await init_queue()
    logger.info("startup.queue_ready")

    logger.info("startup.complete", app_name=settings.APP_NAME)

    yield  # ← Aplicação rodando aqui

    # ── SHUTDOWN ─────────────────────────────────────────────────────────────
    logger.info("shutdown.begin")
    await close_queue()
    await close_db()
    logger.info("shutdown.complete")


# ──────────────────────────────────────────────────────────────────────────────
# Instância principal da aplicação
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description="""
    ## Assistente IA para Atendimento

    API moderna de atendimento automatizado com Inteligência Artificial.

    ### Funcionalidades
    - 📱 **Webhooks** para WhatsApp e Telegram
    - 🤖 **IA Conversacional** com OpenAI GPT-4
    - 💾 **Histórico** completo de conversas
    - 🔄 **Processamento assíncrono** com filas
    - 📊 **Observabilidade** com logs estruturados
    - 🔒 **Segurança** com autenticação e rate limiting

    ### Canais Suportados
    - WhatsApp Business API
    - Telegram Bot API
    """,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.SHOW_DOCS else None,
    redoc_url="/redoc" if settings.SHOW_DOCS else None,
    openapi_url="/openapi.json" if settings.SHOW_DOCS else None,
    lifespan=lifespan,
)

# ──────────────────────────────────────────────────────────────────────────────
# Middlewares (ordem importa — executados de baixo para cima no request)
# ──────────────────────────────────────────────────────────────────────────────

# 1. CORS — deve ser o mais externo
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

# 2. Hosts confiáveis (segurança básica)
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )

# 3. Rate Limiting
app.add_middleware(RateLimitMiddleware)

# 4. Autenticação (exceto rotas públicas)
app.add_middleware(AuthMiddleware)


# ──────────────────────────────────────────────────────────────────────────────
# Middleware de Request ID e timing (via decorator de evento)
# ──────────────────────────────────────────────────────────────────────────────
@app.middleware("http")
async def add_request_context(request: Request, call_next):
    """Adiciona request_id e mede tempo de resposta para cada requisição."""
    import uuid

    request_id = str(uuid.uuid4())[:8]
    start_time = time.perf_counter()

    # Injeta no state para uso nos handlers
    request.state.request_id = request_id

    # Bind no contexto de log
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    response: Response = await call_next(request)

    elapsed = (time.perf_counter() - start_time) * 1000  # ms

    logger.info(
        "http.request",
        status_code=response.status_code,
        duration_ms=round(elapsed, 2),
    )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{elapsed:.2f}ms"

    structlog.contextvars.clear_contextvars()
    return response


# ──────────────────────────────────────────────────────────────────────────────
# Handlers de exceção globais
# ──────────────────────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "Ocorreu um erro interno. Nossa equipe foi notificada.",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Routers
# ──────────────────────────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
app.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
