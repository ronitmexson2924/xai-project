"""The fixes from the security review: shared rate-limit counters, trusted proxies, the guard on
the CPU-heavy endpoints, registration limits, headers on every response, and /health."""

import time
from collections.abc import Iterator

import fakeredis
import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api import heavy
from app.auth.limits import MemoryWindows, RedisWindows, Windows, client_ip, windows
from app.config import Settings, check_production_settings, settings
from tests.api_helpers import API, learner

# --- whose request is it ------------------------------------------------------------------------


def _request(peer: str, **headers: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(k.replace("_", "-").encode(), v.encode()) for k, v in headers.items()],
            "client": (peer, 5000),
        }
    )


def test_forwarded_for_is_ignored_unless_the_deployment_trusts_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "trust_forwarded_for", False)
    assert client_ip(_request("10.1.2.3", x_forwarded_for="6.6.6.6")) == "10.1.2.3"


def test_forwarded_for_counts_only_from_a_trusted_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trust_forwarded_for", True)
    # default: private networks only, so a client on the internet cannot pick its own address
    assert client_ip(_request("203.0.113.9", x_forwarded_for="6.6.6.6")) == "203.0.113.9"
    # from the proxy, the last hop (the one the proxy appended) is the client
    proxied = _request("10.0.0.7", x_forwarded_for="6.6.6.6, 198.51.100.4")
    assert client_ip(proxied) == "198.51.100.4"
    # rubbish in the header falls back to the connection's address
    assert client_ip(_request("10.0.0.7", x_forwarded_for="not-an-ip")) == "10.0.0.7"
    monkeypatch.setattr(settings, "trusted_proxy_ips", "*")  # e.g. Render: every request is proxied
    assert client_ip(_request("203.0.113.9", x_forwarded_for="198.51.100.4")) == "198.51.100.4"
    monkeypatch.setattr(settings, "trusted_proxy_ips", "192.0.2.0/24")
    assert client_ip(_request("192.0.2.10", x_forwarded_for="198.51.100.4")) == "198.51.100.4"
    assert client_ip(_request("10.0.0.7", x_forwarded_for="198.51.100.4")) == "10.0.0.7"


def test_the_frontend_server_can_name_the_browser_only_with_the_shared_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "s" * 40
    monkeypatch.setattr(settings, "proxy_secret", secret)
    named = _request("203.0.113.9", x_proxy_secret=secret, x_client_ip="198.51.100.4")
    assert client_ip(named) == "198.51.100.4"
    forged = _request("203.0.113.9", x_proxy_secret="guess", x_client_ip="198.51.100.4")
    assert client_ip(forged) == "203.0.113.9"
    monkeypatch.setattr(settings, "proxy_secret", "")  # not configured: never trusted
    assert client_ip(_request("203.0.113.9", x_proxy_secret="", x_client_ip="1.2.3.4")) == (
        "203.0.113.9"
    )


def test_production_refuses_a_short_proxy_secret() -> None:
    s = Settings(jwt_secret="j" * 40, cors_origins="https://app.example", proxy_secret="short")
    assert any("PROXY_SECRET" in p for p in check_production_settings(s))
    assert check_production_settings(s.model_copy(update={"proxy_secret": "p" * 32})) == []


# --- counters shared through Redis --------------------------------------------------------------


def test_redis_windows_limit_and_unlock() -> None:
    store = RedisWindows(fakeredis.FakeRedis())
    assert [store.hit("k", 3, 60) for _ in range(3)] == [0, 0, 0]
    assert store.hit("k", 3, 60) > 0
    assert store.hit("other", 3, 60) == 0
    store.add("fail", 60)
    store.add("fail", 60)
    assert store.wait("fail", 2, 60) > 0 and store.wait("fail", 3, 60) == 0
    store.clear("fail")
    assert store.wait("fail", 2, 60) == 0


def test_two_api_instances_share_one_count() -> None:
    server = fakeredis.FakeServer()
    first, second = Windows(), Windows()
    first.use(fakeredis.FakeRedis(server=server))
    second.use(fakeredis.FakeRedis(server=server))
    assert first.hit("ip:1", 2, 60) == 0 and second.hit("ip:1", 2, 60) == 0
    assert first.hit("ip:1", 2, 60) > 0 and second.hit("ip:1", 2, 60) > 0


class _DownRedis:
    def pipeline(self):
        raise redis.ConnectionError("down")

    def delete(self, *_):
        raise redis.ConnectionError("down")


def test_requests_keep_flowing_when_redis_is_down() -> None:
    store = Windows()
    store.use(_DownRedis())
    assert store.hit("k", 1, 60) == 0  # counted in this process instead
    assert store.hit("k", 1, 60) > 0
    assert store._retry_at > 0  # and Redis is left alone for a while, not retried per request
    store.clear("k")


@pytest.fixture
def shared_redis() -> Iterator[fakeredis.FakeRedis]:
    fake = fakeredis.FakeRedis()
    windows.use(fake)
    yield fake
    windows.use(None)


def test_the_api_counts_requests_in_redis_when_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, shared_redis: fakeredis.FakeRedis
) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 2)
    assert [client.get(f"{API}/graph").status_code for _ in range(3)][-1] == 429
    assert any(k.startswith(b"pcg:rl:req:") for k in shared_redis.keys())


def test_a_window_reopens_once_it_has_passed() -> None:
    store = MemoryWindows()
    assert store.hit("k", 1, 0.05) == 0 and store.hit("k", 1, 0.05) > 0
    time.sleep(0.06)
    assert store.hit("k", 1, 0.05) == 0


# --- every response carries the security headers -------------------------------------------------


def test_429_and_413_responses_carry_the_security_headers(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 1)
    client.get(f"{API}/graph")
    limited = client.get(f"{API}/graph")
    too_big = client.post(f"{API}/auth/login", content=b"x" * (70 * 1024))
    for r, code in ((limited, 429), (too_big, 413)):
        assert r.status_code == code
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["cache-control"] == "no-store"


def test_production_hides_the_version_and_adds_hsts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert "version" in client.get("/health").json()
    monkeypatch.setattr(settings, "environment", "production")
    r = client.get("/health")
    assert r.json() == {"status": "ok"}
    assert r.headers["strict-transport-security"].startswith("max-age=")


# --- registration ------------------------------------------------------------------------------


def _sign_up(client: TestClient, n: int):
    return client.post(
        f"{API}/auth/register",
        json={"email": f"probe{n}@example.com", "password": "Password-123", "display_name": "P"},
    )


def test_registration_can_be_closed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "allow_registration", False)
    r = _sign_up(client, 0)
    assert r.status_code == 403 and r.json()["error"]["code"] == "REGISTRATION_CLOSED"


def test_sign_ups_are_limited_per_client_taken_emails_included(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "register_max_per_hour", 3)
    assert _sign_up(client, 1).status_code == 201
    assert _sign_up(client, 1).status_code == 409  # taken: still counts
    assert _sign_up(client, 2).status_code == 201
    r = _sign_up(client, 3)
    assert r.status_code == 429 and r.json()["error"]["code"] == "TOO_MANY_REGISTRATIONS"
    assert int(r.headers["retry-after"]) > 0


# --- the CPU-heavy endpoints --------------------------------------------------------------------


def test_reports_are_limited_per_user(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    bob = learner(client, db)
    bob.questionnaire(3)
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "xai_requests_per_minute", 2)
    codes = [bob.get("/learners/me/report").status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    eve = learner(client, db)  # another learner is not affected
    eve.questionnaire(3)
    assert eve.get("/learners/me/report").status_code == 200


def test_a_busy_server_answers_503_instead_of_queueing_forever(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    bob = learner(client, db)
    bob.questionnaire(3)
    monkeypatch.setattr(settings, "xai_max_concurrent", 1)
    monkeypatch.setattr(settings, "xai_wait_seconds", 0.05)
    slot = heavy._slots.semaphore()
    assert slot.acquire(blocking=False)  # someone else's report is being worked out
    try:
        r = bob.get("/learners/me/report")
        assert r.status_code == 503 and r.json()["error"]["code"] == "SERVER_BUSY"
        assert r.headers["retry-after"] == "5"
        monkeypatch.setattr(heavy._slots, "waiting", heavy.MAX_WAITING)  # queue full: no waiting
        assert bob.get("/learners/me/report").status_code == 503
        monkeypatch.setattr(heavy._slots, "waiting", 0)
    finally:
        slot.release()
    assert bob.get("/learners/me/report").status_code == 200
    assert heavy._slots.waiting == 0
