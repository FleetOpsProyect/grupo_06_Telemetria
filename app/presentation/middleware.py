"""Middlewares para trazabilidad de peticiones y propagación de Correlation ID."""

import time
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.logging import correlation_id_ctx


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Intercepta peticiones HTTP para extraer o asignar un Correlation ID."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        corr_id = request.headers.get("X-Correlation-Id") or str(uuid4())
        token = correlation_id_ctx.set(corr_id)

        start_time = time.perf_counter()
        try:
            response: Response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            response.headers["X-Correlation-Id"] = corr_id
            response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
            return response
        finally:
            correlation_id_ctx.reset(token)
