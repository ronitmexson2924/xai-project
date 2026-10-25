"""Rate limiting, request-size and security-header middleware.

Owner: Mit. Limits are per process (in memory): with several workers each enforces its own
window, so the effective limit is up to workers x the setting. Good enough to stop scripted
abuse; put a proxy-level limit in front for anything stricter.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings

EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}
MAX_BODY_BYTES = 256 * 1024  # the largest legitimate body is a 200-event telemetry batch


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window limiter keyed by any string."""

    def __init__(self, window_seconds: int = 60, max_keys: int = 100_000) -> None:
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._lock = Lock()
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, limit: int) -> int:
        """Record a request; 0 if allowed, else seconds until the next one would be."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            if len(self._requests) > self.max_keys:  # bound memory under a flood of keys
                self._requests.clear()
            history = self._requests[key]
            while history and history[0] <= cutoff:
                history.popleft()
            if len(history) >= limit:
                return max(1, int(history[0] + self.window_seconds - now) + 1)
            history.append(now)
            return 0

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()


global_rate_limiter = SlidingWindowRateLimiter()
auth_rate_limiter = SlidingWindowRateLimiter()


def reset_rate_limiter() -> None:
    global_rate_limiter.reset()
    auth_rate_limiter.reset()


def client_ip(request: Request) -> str:
    # X-Forwarded-For is client-controlled unless a trusted proxy overwrites it
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please slow down.",
            }
        },
        headers={"Retry-After": str(retry_after)},
    )


def limit_auth_attempts(request: Request, email: str) -> None:
    """Login/register: limited per client and per account, so neither one client trying many
    accounts nor many clients trying one account gets far."""
    if not settings.rate_limit_enabled:
        return
    for key, limit in (
        (f"ip:{client_ip(request)}", settings.auth_ip_rate_limit_per_minute),
        (f"email:{email.strip().lower()}", settings.auth_rate_limit_per_minute),
    ):
        if retry := auth_rate_limiter.hit(key, limit):
            raise _too_many(retry)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.rate_limit_enabled or request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        retry = global_rate_limiter.hit(
            f"ip:{client_ip(request)}", settings.rate_limit_requests_per_minute
        )
        if retry:
            err = _too_many(retry)
            return JSONResponse(err.detail, status_code=429, headers=err.headers)
        return await call_next(request)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        length = request.headers.get("content-length")
        too_big = length is not None and (not length.isdigit() or int(length) > MAX_BODY_BYTES)
        if too_big or (
            length is None
            and request.method in ("POST", "PUT", "PATCH")
            and len(await request.body()) > MAX_BODY_BYTES
        ):
            return JSONResponse(
                {"error": {"code": "PAYLOAD_TOO_LARGE", "message": "Request body is too large"}},
                status_code=413,
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if not request.url.path.startswith(("/docs", "/redoc")):
            response.headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
        if settings.environment == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response
