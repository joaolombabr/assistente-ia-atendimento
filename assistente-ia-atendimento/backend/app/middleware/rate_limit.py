"""
Middleware de Rate Limiting usando Redis com sliding window.
Protege a API contra abuso e garante fair use.
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import get_settings

settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting simples por IP usando Redis.
    
    Algoritmo: Contador com TTL (Fixed Window).
    Para produção, considere Sliding Window ou Token Bucket.
    
    Limites:
    - RATE_LIMIT_REQUESTS requisições por RATE_LIMIT_WINDOW segundos
    - Chave: rate_limit:{ip}
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Pula rate limit para health checks
        if request.url.path.startswith("/health"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        key = f"rate_limit:{client_ip}"

        try:
            from app.workers.queue import get_redis
            redis = await get_redis()

            # Incrementa contador
            count = await redis.incr(key)

            # Define expiração apenas na primeira requisição
            if count == 1:
                await redis.expire(key, settings.RATE_LIMIT_WINDOW)

            if count > settings.RATE_LIMIT_REQUESTS:
                ttl = await redis.ttl(key)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": f"Muitas requisições. Tente novamente em {ttl}s",
                        "retry_after": ttl,
                    },
                    headers={"Retry-After": str(ttl)},
                )

            response = await call_next(request)
            # Injeta headers informativos
            response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS)
            response.headers["X-RateLimit-Remaining"] = str(
                max(0, settings.RATE_LIMIT_REQUESTS - count)
            )
            return response

        except Exception:
            # Se Redis falhar, não bloqueia o tráfego (fail open)
            return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extrai IP real considerando proxies reversos."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
