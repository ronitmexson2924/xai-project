"""Brute-force protection for login: failed attempts are counted per email and per client, and
a key with too many recent failures is locked for a while. In-process, like the rate limiter
(one API instance in the pilot)."""

import time
from collections import defaultdict
from threading import Lock

from starlette.requests import Request

from app.config import settings


def client_ip(request: Request) -> str:
    """The caller's address. X-Forwarded-For is client-controlled, so it is only used when the
    deployment says a trusted proxy sets it (TRUST_FORWARDED_FOR); then the last hop is the one
    our proxy appended."""
    if settings.trust_forwarded_for:
        forwarded = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",")]
        if forwarded and forwarded[-1]:
            return forwarded[-1]
    return request.client.host if request.client else "unknown"


class LoginThrottle:
    def __init__(self) -> None:
        self._lock = Lock()
        self._failures: dict[str, list[float]] = defaultdict(list)

    def _recent(self, key: str, now: float) -> list[float]:
        window = settings.login_lockout_seconds
        recent = [t for t in self._failures.get(key, []) if t > now - window]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def retry_after(self, *keys: str) -> int:
        """Seconds until login is allowed again for these keys; 0 if allowed now. Client keys
        ("ip:...") get a larger budget: a classroom can share one address."""
        now = time.time()
        with self._lock:
            waits = [
                int(recent[0] + settings.login_lockout_seconds - now) + 1
                for key in keys
                if len(recent := self._recent(key, now)) >= _limit(key)
            ]
        return max(waits, default=0)

    def failed(self, *keys: str) -> None:
        now = time.time()
        with self._lock:
            for key in keys:
                self._recent(key, now)
                self._failures[key].append(now)

    def succeeded(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._failures.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


def _limit(key: str) -> int:
    return settings.login_max_failures * (IP_MULTIPLIER if key.startswith("ip:") else 1)


IP_MULTIPLIER = 5
login_throttle = LoginThrottle()
