"""Request counting for rate limits and brute-force protection, and the caller's address.

Counters live in Redis when REDIS_URL is set, so every API instance and worker shares them;
otherwise in this process (fine for a single instance). If Redis stops answering, counting falls
back to this process rather than failing requests.

- LoginThrottle: failed logins per email and per client; a key with too many is locked a while.
- client_ip: who is calling, trusting proxy headers only from proxies we know.
"""

import hmac
import ipaddress
import logging
import secrets
import time
from collections import defaultdict
from threading import Lock
from typing import Any

from starlette.requests import Request

from app.config import settings

logger = logging.getLogger("pcg")


def _ip(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def _trusted_proxy(peer: str) -> bool:
    if settings.trusted_proxy_ips.strip() == "*":
        return True
    try:
        address = ipaddress.ip_address(peer)
    except ValueError:
        return False
    for network in settings.trusted_proxy_ips.split(","):
        try:
            if network.strip() and address in ipaddress.ip_network(network.strip(), strict=False):
                return True
        except ValueError:
            logger.warning("ignoring TRUSTED_PROXY_IPS entry %r", network)
    return False


def client_ip(request: Request) -> str:
    """The caller's address.

    1. Our own frontend server forwards requests for browsers (src/app/api); it names the browser
       in X-Client-IP and proves it is the frontend with the shared PROXY_SECRET.
    2. Otherwise X-Forwarded-For, which anyone can send, counts only when the deployment says a
       proxy sets it (TRUST_FORWARDED_FOR) and the request really came from that proxy
       (TRUSTED_PROXY_IPS). Then the last hop is the one the proxy appended.
    3. Otherwise the address the connection came from.
    """
    secret = settings.proxy_secret
    if secret and hmac.compare_digest(
        request.headers.get("x-proxy-secret", "").encode(), secret.encode()
    ):
        if forwarded := _ip(request.headers.get("x-client-ip", "")):
            return forwarded
    peer = request.client.host if request.client else "unknown"
    if settings.trust_forwarded_for and _trusted_proxy(peer):
        hops = request.headers.get("x-forwarded-for", "").split(",")
        if last := _ip(hops[-1]):
            return last
    return peer


class MemoryWindows:
    """Sliding windows of timestamps, per key, in this process."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _recent(self, key: str, now: float, window: float) -> list[float]:
        recent = [t for t in self._hits.get(key, []) if t > now - window]
        if recent:
            self._hits[key] = recent
        else:
            self._hits.pop(key, None)
        return recent

    def hit(self, key: str, limit: int, window: float) -> int:
        """Count a request if the key is under its limit. Returns 0 if counted, otherwise the
        seconds until it would be."""
        now = time.time()
        with self._lock:
            recent = self._recent(key, now, window)
            if len(recent) >= limit:
                return max(1, int(recent[0] + window - now) + 1)
            self._hits[key].append(now)
            if len(self._hits) > 10_000:  # forget idle keys so memory stays bounded
                for k in [k for k, v in self._hits.items() if not v or v[-1] <= now - window]:
                    del self._hits[k]
            return 0

    def wait(self, key: str, limit: int, window: float) -> int:
        """Seconds until the key is under its limit again (0 if it is), without counting."""
        now = time.time()
        with self._lock:
            recent = self._recent(key, now, window)
            return int(recent[0] + window - now) + 1 if len(recent) >= limit else 0

    def add(self, key: str, window: float) -> None:
        now = time.time()
        with self._lock:
            self._recent(key, now, window)
            self._hits[key].append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class RedisWindows:
    """The same windows as sorted sets in Redis (score = time), shared by every instance."""

    PREFIX = "pcg:rl:"

    def __init__(self, client: Any) -> None:
        self.redis = client

    def _trim(self, pipe: Any, key: str, now: float, window: float) -> None:
        pipe.zremrangebyscore(self.PREFIX + key, 0, now - window)

    def hit(self, key: str, limit: int, window: float) -> int:
        now, member = time.time(), secrets.token_hex(8)
        name = self.PREFIX + key
        pipe = self.redis.pipeline()  # MULTI/EXEC: the steps run together
        self._trim(pipe, key, now, window)
        pipe.zadd(name, {member: now})
        pipe.zcard(name)
        pipe.zrange(name, 0, 0, withscores=True)
        pipe.expire(name, int(window) + 1)
        _, _, count, oldest, _ = pipe.execute()
        if count <= limit:
            return 0
        self.redis.zrem(name, member)  # over the limit: this request does not count
        return max(1, int(oldest[0][1] + window - now) + 1)

    def wait(self, key: str, limit: int, window: float) -> int:
        now, name = time.time(), self.PREFIX + key
        pipe = self.redis.pipeline()
        self._trim(pipe, key, now, window)
        pipe.zcard(name)
        pipe.zrange(name, 0, 0, withscores=True)
        _, count, oldest = pipe.execute()
        return int(oldest[0][1] + window - now) + 1 if count >= limit and oldest else 0

    def add(self, key: str, window: float) -> None:
        now, name = time.time(), self.PREFIX + key
        pipe = self.redis.pipeline()
        self._trim(pipe, key, now, window)
        pipe.zadd(name, {secrets.token_hex(8): now})
        pipe.expire(name, int(window) + 1)
        pipe.execute()

    def clear(self, key: str) -> None:
        self.redis.delete(self.PREFIX + key)

    def reset(self) -> None:
        for name in self.redis.scan_iter(match=self.PREFIX + "*"):
            self.redis.delete(name)


REDIS_RETRY_SECONDS = 30


class Windows:
    """Redis when configured and reachable, this process otherwise."""

    def __init__(self) -> None:
        self.memory = MemoryWindows()
        self._redis: RedisWindows | None = None
        self._redis_url = ""
        self._retry_at = 0.0  # after a Redis failure, skip it until then (no timeout per request)

    def _backend(self) -> RedisWindows | None:
        if settings.redis_url != self._redis_url:
            self._redis_url = settings.redis_url
            self._redis = None
            if self._redis_url:
                import redis

                client = redis.Redis.from_url(
                    self._redis_url, socket_timeout=0.5, socket_connect_timeout=0.5
                )
                self._redis = RedisWindows(client)
        return self._redis

    def use(self, client: Any) -> None:
        """Count in this Redis client (tests)."""
        self._redis_url = settings.redis_url
        self._redis = RedisWindows(client) if client is not None else None
        self._retry_at = 0.0

    def _call(self, name: str, *args: Any) -> Any:
        backend = self._backend()
        if backend is not None and time.monotonic() >= self._retry_at:
            try:
                return getattr(backend, name)(*args)
            except Exception:  # Redis down or slow: keep serving, count locally meanwhile
                logger.warning("rate-limit store unavailable; counting in this process for 30 s")
                self._retry_at = time.monotonic() + REDIS_RETRY_SECONDS
        return getattr(self.memory, name)(*args)

    def hit(self, key: str, limit: int, window: float) -> int:
        return self._call("hit", key, limit, window)

    def wait(self, key: str, limit: int, window: float) -> int:
        return self._call("wait", key, limit, window)

    def add(self, key: str, window: float) -> None:
        self._call("add", key, window)

    def clear(self, key: str) -> None:
        self._call("clear", key)

    def reset(self) -> None:
        self.memory.reset()
        if (backend := self._backend()) is not None:
            backend.reset()


windows = Windows()


class LoginThrottle:
    def retry_after(self, *keys: str) -> int:
        """Seconds until login is allowed again for these keys; 0 if allowed now. Client keys
        ("ip:...") get a larger budget: a classroom can share one address."""
        window = settings.login_lockout_seconds
        return max((windows.wait(f"login:{key}", _limit(key), window) for key in keys), default=0)

    def failed(self, *keys: str) -> None:
        for key in keys:
            windows.add(f"login:{key}", settings.login_lockout_seconds)

    def succeeded(self, *keys: str) -> None:
        for key in keys:
            windows.clear(f"login:{key}")

    def reset(self) -> None:
        windows.reset()


def _limit(key: str) -> int:
    return settings.login_max_failures * (IP_MULTIPLIER if key.startswith("ip:") else 1)


IP_MULTIPLIER = 5
login_throttle = LoginThrottle()
