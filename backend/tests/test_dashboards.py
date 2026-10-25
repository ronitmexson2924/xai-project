"""Tests for Open Learner Model and Admin dashboard endpoints.

Owner: Mit.
Verifies demo learners, open learner model states, audit history, graph DAG,
and administrative metrics and CSV exports.
"""

from fastapi.testclient import TestClient

from app.auth.security import create_access_token
from app.auth.store import (
    DEMO_ADVANCED_ID,
    DEMO_INTERMEDIATE_ID,
    DEMO_NOVICE_ID,
)
from app.main import app

client = TestClient(app)


def test_demo_learners_exist_and_can_login():
    """Acceptance: demo seed learners exist in user store and can authenticate."""
    for email in ["novice@example.com", "intermediate@example.com", "advanced@example.com"]:
        res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "Demo1234!"},
        )
        assert res.status_code == 200, f"Failed to login demo learner {email}: {res.text}"
        data = res.json()
        assert "token" in data
        assert data["user"]["consent_at"] is not None


def test_learner_states_and_traits_plain_language_data():
    """Acceptance: /learners/me/state returns rich BKT masteries and traits."""
    for demo_id, expected_arm in [
        (DEMO_NOVICE_ID, "closed_loop"),
        (DEMO_INTERMEDIATE_ID, "static_personalized"),
        (DEMO_ADVANCED_ID, "generic"),
    ]:
        token = create_access_token(demo_id)
        res = client.get(
            "/api/v1/learners/me/state",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        state = res.json()
        assert state["arm"] == expected_arm
        assert "traits" in state
        assert len(state["traits"]["traits"]) == 5
        assert len(state["mastery"]) > 0

    # Novice specific check: has loops and recursion-base-case with misconception
    novice_token = create_access_token(DEMO_NOVICE_ID)
    res = client.get(
        "/api/v1/learners/me/state",
        headers={"Authorization": f"Bearer {novice_token}"},
    )
    novice_data = res.json()
    assert "loops" in novice_data["mastery"]
    assert "recursion-base-case" in novice_data["mastery"]
    assert len(novice_data["mastery"]["recursion-base-case"]["misconception_ids"]) > 0


def test_learner_history_why_we_think_this():
    """Acceptance: /learners/me/history returns chronological audit updates."""
    token = create_access_token(DEMO_NOVICE_ID)
    res = client.get(
        "/api/v1/learners/me/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    history = res.json()
    assert len(history) >= 4

    sources = {h["source"] for h in history}
    assert "questionnaire" in sources
    assert "attempt" in sources
    assert "explanation_feedback" in sources


def test_graph_endpoint_returns_dag():
    """Acceptance: /graph returns all concepts and prerequisite edges."""
    token = create_access_token(DEMO_NOVICE_ID)
    res = client.get(
        "/api/v1/graph",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    concepts = data["concepts"]
    edges = data["edges"]

    assert len(concepts) >= 40
    assert len(edges) >= 30

    concept_ids = {c["id"] for c in concepts}
    for e in edges:
        assert e["src"] in concept_ids, f"Edge src {e['src']} not in concepts"
        assert e["dst"] in concept_ids, f"Edge dst {e['dst']} not in concepts"


def test_admin_metrics_and_csv_exports():
    """Acceptance: /admin/metrics returns SLA latencies, arm mix, and CSV export works."""
    token = create_access_token(DEMO_ADVANCED_ID)

    # 1. Metrics
    res = client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    metrics = res.json()
    assert metrics["total_users"] >= 3
    assert "closed_loop" in metrics["arm_distribution"]
    assert metrics["p50_latency_ms"] <= 100.0
    assert metrics["p95_latency_ms"] <= 100.0
    assert "source_mix" in metrics
    assert "clarity_distribution" in metrics

    # 2. CSV Exports
    for table in ["users", "assignments", "attempts"]:
        res = client.get(
            f"/api/v1/admin/export.csv?table={table}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/csv")
        csv_text = res.text
        assert len(csv_text.strip().split("\n")) >= 2
