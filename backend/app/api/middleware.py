"""Rate limiting and security middleware for FastAPI.

Owner: Mit.
- RateLimitMiddleware: sliding-window limit per client address (in memory: one API instance).
- SecurityHeadersMiddleware: no sniffing, no framing, no caching of personal data.
- BodySizeLimitMiddleware: rejects oversized request bodies before they are parsed.
"""

import time
from collections import defaultdict
from threading import Lock

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.auth.limits import client_ip

EXEMPT_PATHS = {"/health", "/health/ready", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}
MAX_BODY_BYTES = 64 * 1024


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
            valid = [ts for ts in self._requests[client_key] if ts > cutoff]
            if len(valid) >= self.max_requests:
                self._requests[client_key] = valid
                return False, max(1, int(valid[0] + self.window_seconds - now))
            valid.append(now)
            self._requests[client_key] = valid
            if len(self._requests) > 10_000:  # forget idle clients so memory stays bounded
                for key in [k for k, v in self._requests.items() if not v or v[-1] <= cutoff]:
                    del self._requests[key]
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()


global_rate_limiter = SlidingWindowRateLimiter()


def reset_rate_limiter() -> None:
    global_rate_limiter.reset()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: SlidingWindowRateLimiter | None = None) -> None:
        super().__init__(app)
        self.limiter = limiter or global_rate_limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        from app.config import settings

        if not settings.rate_limit_enabled or request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        self.limiter.max_requests = settings.rate_limit_requests_per_minute
        allowed, retry_after = self.limiter.is_allowed(client_ip(request))
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


class BodySizeLimitMiddleware:
    """Pure ASGI: counts bytes as they arrive, so a lying Content-Length cannot get past it."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.max_bytes):
            await _too_large(scope, receive, send)
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await _too_large(scope, receive, send)


class _BodyTooLarge(Exception):
    pass


async def _too_large(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse(
        status_code=413,
        content={"error": {"code": "PAYLOAD_TOO_LARGE", "message": "Request body is too large"}},
    )
    await response(scope, receive, send)
