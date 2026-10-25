"""Rate limiting and security middleware for FastAPI.

Owner: Mit.
Implements sliding-window in-memory rate limiting per client IP.
"""

import time
from collections import defaultdict
from threading import Lock

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

EXEMPT_PATHS = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
}


class SlidingWindowRateLimiter:
    """Thread-safe sliding window rate limiter."""

    def __init__(self, max_requests: int = 120, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_key: str) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            history = self._requests[client_key]
            # Prune timestamps older than window
            valid = [ts for ts in history if ts > cutoff]
            self._requests[client_key] = valid

            if len(valid) >= self.max_requests:
                oldest = valid[0]
                retry_after = max(1, int(oldest + self.window_seconds - now))
                return False, retry_after

            valid.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()


global_rate_limiter = SlidingWindowRateLimiter()


def reset_rate_limiter() -> None:
    """Clears all client request history in rate limiter."""
    global_rate_limiter.reset()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        max_requests: int = 120,
        window_seconds: int = 60,
        enabled: bool = True,
        limiter: SlidingWindowRateLimiter | None = None,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.limiter = limiter or global_rate_limiter
        self.limiter.max_requests = max_requests
        self.limiter.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        from app.config import settings

        if not (self.enabled and settings.rate_limit_enabled) or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # Synchronize dynamic configuration
        self.limiter.max_requests = settings.rate_limit_requests_per_minute

        # Use X-Forwarded-For if behind proxy, else client host
        client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )

        allowed, retry_after = self.limiter.is_allowed(client_ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please slow down.",
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
