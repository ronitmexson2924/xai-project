"""M7/M8: rate limiting, retention purge, cohort onboarding, explanation audit and ops (Postgres).

Owner: Mit. Replaces the in-memory versions of these tests (test_experiment_infra, test_pilot_ops).
"""

from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.middleware import SlidingWindowRateLimiter
from app.api.ops import get_pilot_ops_status
from app.auth.onboard import create_admin, generate_secure_password, onboard_cohort
from app.auth.purge import purge_soft_deleted_users
from app.auth.security import hash_password
from app.auth.store import get_user_by_email, register_user
from app.config import Settings, check_production_settings, settings
from app.db import models as m
from app.explainer.audit import compute_cohens_kappa, score
from tests.api_helpers import API, register


def test_sliding_window_rate_limiter() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)
    for _ in range(5):
        assert limiter.is_allowed("192.168.1.100") == (True, 0)
    allowed, retry_after = limiter.is_allowed("192.168.1.100")
    assert not allowed and retry_after > 0
    assert limiter.is_allowed("192.168.1.101") == (True, 0)  # per client


def test_rate_limiting_middleware(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 3)
    for _ in range(3):
        assert client.get(f"{API}/graph").status_code != 429
    r = client.get(f"{API}/graph")
    assert r.status_code == 429 and "Retry-After" in r.headers
    assert r.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert client.get("/health").status_code == 200  # health checks are exempt


def test_purge_respects_retention(db: Session) -> None:
    now = datetime.now(UTC)
    ids = {
        name: register_user(db, f"{name}@example.com", hash_password("Password123!"), name)[0].id
        for name in ("active", "recent", "old")
    }
    db.execute(
        update(m.User).where(m.User.id == ids["recent"]).values(deleted_at=now - timedelta(5))
    )
    db.execute(update(m.User).where(m.User.id == ids["old"]).values(deleted_at=now - timedelta(40)))
    assert purge_soft_deleted_users(db, retention_days=30) == 1
    db.expire_all()
    assert db.get(m.User, ids["old"]) is None
    assert db.get(m.User, ids["recent"]) is not None
    assert get_user_by_email(db, "active@example.com") is not None


def test_generate_secure_password() -> None:
    pwd = generate_secure_password(length=14)
    assert len(pwd) == 14
    assert any(c.islower() for c in pwd) and any(c.isupper() for c in pwd)
    assert any(c.isdigit() for c in pwd) and any(c in "!@#$%^&*" for c in pwd)


def test_onboard_cohort_is_balanced_and_rerunnable(db: Session, tmp_path: Path) -> None:
    roster = tmp_path / "cohort.roster.csv"
    cohort = onboard_cohort(db, 45, "pilot", "university.edu", roster)
    assert len(cohort) == 45 and roster.exists()
    assert Counter(p["arm"] for p in cohort) == {
        "generic": 15,
        "static_personalized": 15,
        "closed_loop": 15,
    }
    assert onboard_cohort(db, 46, "pilot", "university.edu") != []  # only the missing one is added
    assert len(onboard_cohort(db, 46, "pilot", "university.edu")) == 0


def test_create_admin_and_admin_only_routes(client: TestClient, db: Session) -> None:
    create_admin(db, "boss@example.com", "Admin-password-1")
    db.commit()
    with pytest.raises(ValueError):
        create_admin(db, "weak@example.com", "short")
    token = client.post(
        f"{API}/auth/login", json={"email": "boss@example.com", "password": "Admin-password-1"}
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"{API}/ops/status", headers=headers).status_code == 200
    learner = register(client)
    assert learner.get("/ops/status").status_code == 403


def test_ops_status_is_measured(db: Session, client: TestClient) -> None:
    status = get_pilot_ops_status(db)
    assert status.concepts_count >= 50 and status.approved_items_count > 0
    assert status.explanation_p95_ms_24h is None  # nothing measured yet, so nothing claimed


def test_cohens_kappa() -> None:
    assert compute_cohens_kappa(["a", "b", "c", "a"], ["a", "b", "c", "a"])[0] == 1.0
    r1 = ["correct"] * 88 + ["minor_issue"] * 11 + ["wrong"]
    r2 = ["correct"] * 87 + ["minor_issue"] * 12 + ["wrong"]
    kappa, p_o, _ = compute_cohens_kappa(r1, r2)
    assert kappa > 0.85 and p_o >= 0.95
    with pytest.raises(ValueError):
        compute_cohens_kappa([], [])


def test_audit_refuses_missing_human_ratings() -> None:
    row = {"id": "audit-001", "auto_grounded": "True", "rater_mit": "correct", "rater_ronit": ""}
    with pytest.raises(ValueError, match="rater_ronit"):
        score([row])
    stats = score([row | {"rater_ronit": "correct"}])
    assert stats["kappa"] == 1.0 and stats["auto_grounded_pct"] == 100.0


def test_production_refuses_unsafe_settings() -> None:
    unsafe = Settings(jwt_secret="change-me", cors_origins="*")
    assert len(check_production_settings(unsafe)) == 2
    safe = Settings(jwt_secret="x" * 40, cors_origins="https://pcg.example.org")
    assert check_production_settings(safe) == []
