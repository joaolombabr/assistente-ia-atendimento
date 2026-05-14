"""
Middleware de autenticação via API Key.
Rotas públicas são listadas explicitamente no SKIP_AUTH_PATHS.
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import get_settings

settings = get_settings()

# Rotas que NÃO precisam de autenticação
SKIP_AUTH_PATHS = {
    "/health",
    "/health/live",
    "/health/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    # Webhooks usam verificação própria (assinatura Meta / Telegram token)
    "/webhooks/whatsapp",
    "/webhooks/telegram",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Valida o header X-API-Key em todas as rotas protegidas.
    
    Para usar no cliente:
        headers = {"X-API-Key": "sua-chave-aqui"}
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Libera rotas públicas
        if path in SKIP_AUTH_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        api_key = request.headers.get(settings.API_KEY_HEADER)

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "API Key ausente"},
            )

        if api_key != settings.INTERNAL_API_KEY:
            return JSONResponse(
                status_code=403,
                content={"error": "forbidden", "message": "API Key inválida"},
            )

        return await call_next(request)
