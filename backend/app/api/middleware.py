"""Rate limiting and security middleware for FastAPI.

Owner: Mit.
- RateLimitMiddleware: sliding-window limit per client address (shared through Redis when
  REDIS_URL is set, see app/auth/limits.py).
- SecurityHeadersMiddleware: no sniffing, no framing, no caching of personal data. It is the
  outermost middleware, so every response gets the headers, including 413s and 429s.
- BodySizeLimitMiddleware: rejects oversized request bodies before they are parsed.
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.auth.limits import MemoryWindows, Windows, client_ip, windows
from app.config import settings

EXEMPT_PATHS = {"/health", "/health/ready", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}
MAX_BODY_BYTES = 64 * 1024


class SlidingWindowRateLimiter:
    """At most max_requests per client in any window_seconds."""

    def __init__(
        self,
        max_requests: int = 120,
        window_seconds: int = 60,
        store: Windows | MemoryWindows | None = None,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.store = store or MemoryWindows()

    def is_allowed(self, client_key: str) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        wait = self.store.hit(f"req:{client_key}", self.max_requests, self.window_seconds)
        return wait == 0, wait

    def reset(self) -> None:
        self.store.reset()


global_rate_limiter = SlidingWindowRateLimiter(store=windows)


def reset_rate_limiter() -> None:
    global_rate_limiter.reset()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: SlidingWindowRateLimiter | None = None) -> None:
        super().__init__(app)
        self.limiter = limiter or global_rate_limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
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


class SecurityHeadersMiddleware:
    """Pure ASGI, so it can wrap everything else and add headers to every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = scope["path"].startswith("/api/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "no-referrer")
                if settings.environment == "production":
                    headers.setdefault("Strict-Transport-Security", "max-age=31536000")
                if is_api:
                    headers.setdefault("Cache-Control", "no-store")
                    # JSON only: nothing here may load or run anything if opened in a browser
                    headers.setdefault(
                        "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
                    )
            await send(message)

        await self.app(scope, receive, send_with_headers)


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
