"""
Security Hardening and Defense-in-Depth Middleware (ContextIQ Phase 7.9).
Enforces:
1. Production HTTP Security Headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options, etc.).
2. Request Payload Size Limits (rejects > 5MB with 413 Payload Too Large).
3. Client-level Rate Limiting with sliding windows and Retry-After headers (429 Too Many Requests).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Maximum permitted payload body size (5 MB)
MAX_REQUEST_BODY_BYTES = 5 * 1024 * 1024

# Default sliding window rate limit (requests per minute)
DEFAULT_RATE_LIMIT_PER_MINUTE = 180
WINDOW_SECONDS = 60.0

# Paths exempt from rate limiting (health probes, docs)
EXEMPT_PATHS: Set[str] = {
    "/health",
    "/health/live",
    "/health/ready",
    "/live",
    "/ready",
    "/api/v1/health",
    "/api/v1/health/live",
    "/api/v1/health/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class RateLimiter:
    """Thread-safe sliding-window in-memory rate limiter per client IP."""

    def __init__(self, requests_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE) -> None:
        self.requests_per_minute = requests_per_minute
        self._windows: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        cutoff = now - WINDOW_SECONDS

        with self._lock:
            q = self._windows[client_id]
            # Evict timestamps outside the sliding window
            while q and q[0] < cutoff:
                q.popleft()

            if len(q) >= self.requests_per_minute:
                return False

            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()

    def set_limit(self, limit: int) -> None:
        with self._lock:
            self.requests_per_minute = limit


# Global rate limiter instance
rate_limiter = RateLimiter()


class SecurityHardeningMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive HTTP security middleware guarding against:
    - Injection attacks, clickjacking, MIME-sniffing
    - Large payload memory exhaustion (DoS)
    - High-frequency brute force and API abuse
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # 1. Request Body Size Limit Check (413 Payload Too Large)
        content_length_header = request.headers.get("content-length")
        if content_length_header:
            try:
                content_length = int(content_length_header)
                if content_length > MAX_REQUEST_BODY_BYTES:
                    logger.warning(
                        "Blocked request to %s: Content-Length %d exceeds limit %d",
                        path,
                        content_length,
                        MAX_REQUEST_BODY_BYTES,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "Payload Too Large",
                            "detail": f"Request body exceeds the maximum permitted size of {MAX_REQUEST_BODY_BYTES // (1024 * 1024)}MB.",
                        },
                    )
            except ValueError:
                pass

        # 2. Rate Limiting Check (429 Too Many Requests)
        if path not in EXEMPT_PATHS:
            client_ip = (
                request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or (request.client.host if request.client else "unknown")
            )
            if not rate_limiter.is_allowed(client_ip):
                logger.warning("Rate limit exceeded for client %s on %s", client_ip, path)
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": "60"},
                    content={
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Please wait before submitting additional requests.",
                    },
                )

        # 3. Process Request
        response: Response = await call_next(request)

        # 4. Inject Production Security Headers
        headers = response.headers
        headers["X-Content-Type-Options"] = "nosniff"
        headers["X-Frame-Options"] = "DENY"
        headers["X-XSS-Protection"] = "1; mode=block"
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), microphone=(), payment=(), usb=()"
        )
        headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: https:; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self' https:; frame-ancestors 'none';"
        )

        settings = get_settings()
        if settings.APP_ENV == "production" or request.url.scheme == "https":
            headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        return response
