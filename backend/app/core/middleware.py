"""
Observability and Distributed Tracing Middleware (ContextIQ Phase 7.8).
Injects correlation IDs, tracks request latencies, and updates operational metrics.
"""
from __future__ import annotations

import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import (
    correlation_id_ctx,
    request_id_ctx,
    user_id_ctx,
)
from app.core.metrics import metrics_registry


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware that establishes distributed tracing context and records
    real-time API latencies and status codes into MetricsRegistry.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 1. Resolve or generate tracing identifiers
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        corr_id = request.headers.get("X-Correlation-ID") or req_id
        uid = request.headers.get("X-User-Id")

        # Set context variables for structured logger
        req_token = request_id_ctx.set(req_id)
        corr_token = correlation_id_ctx.set(corr_id)
        user_token = user_id_ctx.set(uid)

        start_time = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            metrics_registry.record_request(status_code=status_code, duration_ms=duration_ms)

            # Reset context variables
            request_id_ctx.reset(req_token)
            correlation_id_ctx.reset(corr_token)
            user_id_ctx.reset(user_token)

        # Inject tracing and performance response headers
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Correlation-ID"] = corr_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)

        return response
