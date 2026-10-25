"""Tests for M7: Experiment infrastructure, arm flags, rate limiting, and audit.

Owner: Mit.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_learner_model_service, reset_services
from app.api.flags import get_arm_features
from app.api.middleware import SlidingWindowRateLimiter, reset_rate_limiter
from app.auth import auth_store
from app.auth.models import ExperimentAssignment
from app.auth.purge import purge_soft_deleted_users
from app.auth.security import create_access_token, hash_password
from app.auth.store import InMemoryUserStore
from app.config import settings
from app.contracts.explanation import StyleParams
from app.contracts.learner import LearnerState, LearnerTraits, TraitEstimate
from app.explainer.audit import compute_cohens_kappa, run_llm_audit
from app.main import app


@pytest.fixture(autouse=True)
def clean_environment() -> None:
    auth_store.clear()
    reset_services()
    reset_rate_limiter()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_arm_feature_flags_definition():
    """Validates policy separation between study arms."""
    generic_flags = get_arm_features("generic")
    assert generic_flags.arm == "generic"
    assert generic_flags.allow_trait_personalization is False
    assert generic_flags.allow_closed_loop_feedback is False
    assert generic_flags.allow_exploration is False
    assert generic_flags.forced_style == StyleParams(
        example_first=False, length="medium", depth="how", tone="neutral", include_diagram=False
    )

    static_flags = get_arm_features("static_personalized")
    assert static_flags.arm == "static_personalized"
    assert static_flags.allow_trait_personalization is True
    assert static_flags.allow_closed_loop_feedback is False
    assert static_flags.allow_exploration is False
    assert static_flags.forced_style is None

    closed_flags = get_arm_features("closed_loop")
    assert closed_flags.arm == "closed_loop"
    assert closed_flags.allow_trait_personalization is True
    assert closed_flags.allow_closed_loop_feedback is True
    assert closed_flags.allow_exploration is True
    assert closed_flags.forced_style is None


def test_session_style_respects_arm_flags(client: TestClient):
    """Verifies that generic arm receives fixed style and static personalized uses traits."""
    now = datetime.now(UTC)

    # 1. Register users in generic and static_personalized arms
    u_gen, _ = auth_store.register_user(
        "gen@test.edu", hash_password("Password123!"), "Generic User"
    )
    u_gen.consent_at = now
    auth_store._assignments_by_user_id[u_gen.id] = ExperimentAssignment(
        user_id=u_gen.id, arm="generic", assigned_at=now
    )
    token_gen = create_access_token(u_gen.id)

    u_static, _ = auth_store.register_user(
        "static@test.edu", hash_password("Password123!"), "Static User"
    )
    u_static.consent_at = now
    auth_store._assignments_by_user_id[u_static.id] = ExperimentAssignment(
        user_id=u_static.id, arm="static_personalized", assigned_at=now
    )
    token_static = create_access_token(u_static.id)

    # Initialize learner model states
    learner_model = get_learner_model_service()
    for u in (u_gen, u_static):
        assignment = auth_store.get_assignment(u.id)
        arm = assignment.arm if assignment else "generic"
        st = LearnerState(
            user_id=u.id,
            arm=arm,
            mastery={},
            traits=LearnerTraits(
                traits={
                    "abstraction_preference": TraitEstimate(mean=0.9, variance=0.01),
                    "load_tolerance": TraitEstimate(mean=0.5, variance=0.05),
                    "depth_preference": TraitEstimate(mean=0.8, variance=0.01),
                }
            ),
        )
        if hasattr(learner_model, "_states"):
            learner_model._states[u.id] = st

    # Generic user calls /api/v1/session/next -> must receive generic style
    resp_gen = client.post(
        "/api/v1/session/next",
        headers={"Authorization": f"Bearer {token_gen}"},
    )
    assert resp_gen.status_code == 200
    gen_data = resp_gen.json()
    assert gen_data["explanation"]["style_source"] == "generic"
    assert gen_data["explanation"]["style"]["example_first"] is False
    assert gen_data["explanation"]["style"]["depth"] == "how"

    # Static personalized user calls /api/v1/session/next -> receives trait_mapped style
    resp_static = client.post(
        "/api/v1/session/next",
        headers={"Authorization": f"Bearer {token_static}"},
    )
    assert resp_static.status_code == 200
    static_data = resp_static.json()
    assert static_data["explanation"]["style_source"] == "trait_mapped"
    assert static_data["explanation"]["style"]["depth"] == "why"


def test_sliding_window_rate_limiter():
    """Tests in-memory sliding window rate limiting."""
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)
    client_ip = "192.168.1.100"

    # 5 requests should all be allowed
    for _ in range(5):
        allowed, retry_after = limiter.is_allowed(client_ip)
        assert allowed is True
        assert retry_after == 0

    # 6th request is rejected
    allowed, retry_after = limiter.is_allowed(client_ip)
    assert allowed is False
    assert retry_after > 0


def test_rate_limiting_middleware(client: TestClient):
    """Tests rate limit HTTP 429 response when limit is exceeded."""
    orig_enabled = settings.rate_limit_enabled
    orig_rpm = settings.rate_limit_requests_per_minute

    try:
        settings.rate_limit_enabled = True
        settings.rate_limit_requests_per_minute = 3

        # 3 requests succeed (or return standard non-429 codes)
        for _ in range(3):
            res = client.get("/api/v1/onboarding/questionnaire")
            assert res.status_code != 429

        # 4th request triggers 429
        res = client.get("/api/v1/onboarding/questionnaire")
        assert res.status_code == 429
        assert "Retry-After" in res.headers
        assert res.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    finally:
        settings.rate_limit_enabled = orig_enabled
        settings.rate_limit_requests_per_minute = orig_rpm


def test_user_soft_delete_and_purge():
    """Tests GDPR D11 user purge job."""
    store = InMemoryUserStore(seed_demos=False)
    now = datetime.now(UTC)

    # User 1: Active
    u1, _ = store.register_user("u1@example.com", hash_password("Password123!"), "Active User")

    # User 2: Deleted recently (within retention window, e.g. 5 days ago)
    u2, _ = store.register_user("u2@example.com", hash_password("Password123!"), "Recent Delete")
    u2.deleted_at = now - timedelta(days=5)

    # User 3: Deleted 40 days ago (outside 30-day retention window)
    u3, _ = store.register_user("u3@example.com", hash_password("Password123!"), "Old Delete")
    u3.deleted_at = now - timedelta(days=40)

    # Run purge job with 30-day retention
    purged = purge_soft_deleted_users(store, retention_days=30)
    assert purged == 1

    # u3 is anonymized and email removed from login lookup
    assert store.get_user_by_id(u3.id) is None
    record_u3 = store._users_by_id[u3.id]
    assert record_u3.email.endswith("@purged.local")
    assert record_u3.password_hash == ""
    assert "u3@example.com" not in store._users_by_email

    # u1 and u2 retain their credentials
    active_u1 = store.get_user_by_id(u1.id)
    assert active_u1 is not None
    assert active_u1.email == "u1@example.com"
    assert active_u1.password_hash != ""

    assert store.get_user_by_id(u2.id) is None
    record_u2 = store._users_by_id[u2.id]
    assert record_u2.email == "u2@example.com"
    assert record_u2.password_hash != ""


def test_cohens_kappa_calculation():
    """Validates multi-class Cohen's kappa math."""
    # Perfect agreement
    r1 = ["a", "b", "c", "a", "b"]
    r2 = ["a", "b", "c", "a", "b"]
    kappa, po, pe = compute_cohens_kappa(r1, r2)
    assert kappa == 1.0
    assert po == 1.0

    # High agreement (90%)
    r1 = ["correct"] * 90 + ["minor_issue"] * 10
    r2 = ["correct"] * 90 + ["minor_issue"] * 10
    kappa, po, pe = compute_cohens_kappa(r1, r2)
    assert kappa == 1.0
    assert po == 1.0

    # Slight disagreement
    r1 = ["correct"] * 88 + ["minor_issue"] * 11 + ["wrong"] * 1
    r2 = ["correct"] * 87 + ["minor_issue"] * 12 + ["wrong"] * 1
    kappa, po, pe = compute_cohens_kappa(r1, r2)
    assert kappa > 0.85
    assert po >= 0.95


def test_llm_audit_execution():
    """Runs LLM audit to verify kappa and wrong rate targets."""
    items, stats = run_llm_audit(sample_size=100)
    assert len(items) == 100
    assert stats["cohens_kappa"] >= 0.85
    assert stats["wrong_rate_pct"] < 2.0
    assert stats["grounded_pct"] == 100.0
    assert stats["prompt_acceptable"] is True
