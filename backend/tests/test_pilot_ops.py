"""Automated tests for M8: Pilot operations, cohort onboarding, and system health.

Owner: Mit.
"""

from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import reset_services
from app.api.ops import get_pilot_ops_status
from app.auth import auth_store
from app.auth.onboard import generate_secure_password, onboard_cohort
from app.auth.security import create_access_token
from app.auth.store import DEMO_NOVICE_ID, InMemoryUserStore
from app.main import app


@pytest.fixture(autouse=True)
def clean_environment() -> None:
    auth_store.clear()
    reset_services()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_generate_secure_password():
    """Verifies that generated temporary passwords satisfy security constraints."""
    pwd = generate_secure_password(length=14)
    assert len(pwd) == 14
    assert any(c.islower() for c in pwd)
    assert any(c.isupper() for c in pwd)
    assert any(c.isdigit() for c in pwd)
    assert any(c in "!@#$%^&*" for c in pwd)


def test_onboard_cohort_balanced_distribution(tmp_path: Path):
    """Tests batch student provisioning and balanced arm distribution."""
    store = InMemoryUserStore(seed_demos=False)
    csv_file = tmp_path / "test_cohort.csv"

    cohort = onboard_cohort(
        count=45,
        email_prefix="pilot",
        domain="university.edu",
        store=store,
        csv_output_path=csv_file,
    )

    assert len(cohort) == 45
    assert csv_file.exists()

    # Verify balanced arm distribution across the 3 arms
    arm_counts = Counter(p["arm"] for p in cohort)
    assert arm_counts["generic"] == 15
    assert arm_counts["static_personalized"] == 15
    assert arm_counts["closed_loop"] == 15

    # Verify store records exist
    for p in cohort:
        user = store.get_user_by_email(p["email"])
        assert user is not None
        assert user.display_name == p["display_name"]
        assignment = store.get_assignment(user.id)
        assert assignment is not None
        assert assignment.arm == p["arm"]


def test_pilot_ops_health_status():
    """Verifies operational health metrics and SLA budgets."""
    status = get_pilot_ops_status()
    assert status.system_status == "healthy"
    assert status.concepts_count == 48
    assert status.approved_items_count >= 180
    assert status.sla_budgets_satisfied is True
    assert "next_recommendation" in status.latency_slas
    assert "explanation_dispatch" in status.latency_slas


def test_ops_endpoint_via_client(client: TestClient):
    """Tests GET /api/v1/ops/status endpoint with authenticated user."""
    token = create_access_token(DEMO_NOVICE_ID)
    resp = client.get(
        "/api/v1/ops/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["system_status"] == "healthy"
    assert data["concepts_count"] == 48
    assert data["approved_items_count"] >= 180
    assert data["sla_budgets_satisfied"] is True
