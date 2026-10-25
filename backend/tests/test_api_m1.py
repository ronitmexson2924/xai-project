from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_graph_service, reset_services
from app.api.learners import clear_audit_history
from app.auth import auth_store
from app.main import app


@pytest.fixture(autouse=True)
def clean_environment() -> None:
    auth_store.clear()
    reset_services()
    clear_audit_history()


def test_full_closed_loop_api_workflow() -> None:
    """Test full closed-loop through the API with fakes:

    register -> login -> consent -> questionnaire -> next -> events -> attempt -> state changed.
    """
    client = TestClient(app)

    # 1. Register learner
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "learner_loop@test.edu",
            "password": "securepassword123",
            "display_name": "Grace Hopper",
        },
    )
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    token = auth_data["token"]
    user = auth_data["user"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Verify consent guard blocks access before consent
    blocked_next = client.post("/api/v1/session/next", headers=headers)
    assert blocked_next.status_code == 403
    assert blocked_next.json()["error"]["code"] == "CONSENT_REQUIRED"

    # 3. Give consent
    consent_resp = client.post("/api/v1/auth/consent", headers=headers)
    assert consent_resp.status_code == 200
    assert consent_resp.json()["consent_at"] is not None

    # 4. Fetch questionnaire items
    q_get = client.get("/api/v1/onboarding/questionnaire", headers=headers)
    assert q_get.status_code == 200
    q_items = q_get.json()
    assert len(q_items) >= 5

    # 5. Submit intake answers to initialize traits
    answers = {item["id"]: 4 for item in q_items}
    q_post = client.post(
        "/api/v1/onboarding/questionnaire",
        headers=headers,
        json={"answers": answers},
    )
    assert q_post.status_code == 200
    init_delta = q_post.json()
    assert init_delta["source"] == "questionnaire"

    # 6. Request next step recommendation (/session/next)
    next_resp = client.post("/api/v1/session/next", headers=headers)
    assert next_resp.status_code == 200
    next_data = next_resp.json()

    rec = next_data["recommendation"]
    explanation = next_data["explanation"]
    item = next_data["item"]

    assert rec["user_id"] == user["id"]
    assert rec["target_concept_id"]
    assert len(rec["reasons"]) > 0

    assert explanation["recommendation_id"] == rec["id"]
    assert explanation["body_markdown"]
    assert explanation["style"]
    assert explanation["source"] in ("precomputed", "llm", "template")

    assert item is not None
    # CRITICAL: Verify item answer is NEVER leaked in public item!
    assert "answer" not in item
    assert item["id"]
    assert item["stem"]
    assert len(item["options"]) > 0

    # 7. Ingest telemetry events for the explanation
    exp_id = explanation["id"]
    t0 = datetime.now(UTC)
    events = [
        {
            "idempotency_key": str(uuid4()),
            "type": "shown",
            "client_ts": t0.isoformat(),
            "payload": {},
        },
        {
            "idempotency_key": str(uuid4()),
            "type": "expanded",
            "client_ts": (t0 + timedelta(seconds=2)).isoformat(),
            "payload": {},
        },
        {
            "idempotency_key": str(uuid4()),
            "type": "clarity_rated",
            "client_ts": (t0 + timedelta(seconds=12)).isoformat(),
            "payload": {"rating": 5},
        },
        {
            "idempotency_key": str(uuid4()),
            "type": "dismissed",
            "client_ts": (t0 + timedelta(seconds=15)).isoformat(),
            "payload": {},
        },
    ]

    ev_resp = client.post(
        f"/api/v1/explanations/{exp_id}/events",
        headers=headers,
        json={"events": events},
    )
    assert ev_resp.status_code == 200
    assert ev_resp.json() == {"accepted": 4, "duplicates": 0}

    # Verify idempotency of telemetry events
    ev_dup = client.post(
        f"/api/v1/explanations/{exp_id}/events",
        headers=headers,
        json={"events": events},
    )
    assert ev_dup.status_code == 200
    assert ev_dup.json() == {"accepted": 0, "duplicates": 4}

    # 8. Fetch explanation details
    get_exp = client.get(f"/api/v1/explanations/{exp_id}", headers=headers)
    assert get_exp.status_code == 200
    assert get_exp.json()["id"] == exp_id

    # 9. Submit attempt for the micro-check item linked to the explanation
    target_answer = get_graph_service().get_item(item["id"]).answer
    attempt_resp = client.post(
        "/api/v1/attempts",
        headers=headers,
        json={
            "item_id": item["id"],
            "response": target_answer,
            "latency_ms": 3500,
            "hints_used": 0,
            "confidence": 4,
            "recommendation_id": rec["id"],
            "explanation_id": exp_id,
        },
    )
    assert attempt_resp.status_code == 200
    attempt_data = attempt_resp.json()
    assert attempt_data["correct"] is True
    delta = attempt_data["delta"]
    assert item["concept_id"] in delta["mastery_changes"]

    # 10. Check learner state reflecting mastery update
    state_resp = client.get("/api/v1/learners/me/state", headers=headers)
    assert state_resp.status_code == 200
    state_data = state_resp.json()
    assert state_data["total_attempts"] == 1
    assert item["concept_id"] in state_data["mastery"]

    # 11. Check audit history ("Why we think this")
    history_resp = client.get("/api/v1/learners/me/history", headers=headers)
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) >= 2  # questionnaire + attempt (+ feedback)

    # 12. Check concept graph endpoint
    graph_resp = client.get("/api/v1/graph", headers=headers)
    assert graph_resp.status_code == 200
    graph_data = graph_resp.json()
    assert len(graph_data["concepts"]) >= 2
    assert len(graph_data["edges"]) >= 1

    # 13. Check admin metrics
    metrics_resp = client.get("/api/v1/admin/metrics", headers=headers)
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.json()
    assert metrics_data["total_users"] >= 1
    assert metrics_data["total_attempts"] >= 1

    # 14. Check admin CSV export
    export_resp = client.get("/api/v1/admin/export.csv?table=users", headers=headers)
    assert export_resp.status_code == 200
    assert "text/csv" in export_resp.headers["content-type"]
    assert "pseudonym_id" in export_resp.text


def test_openapi_contract_models_completeness() -> None:
    """Acceptance check: OpenAPI includes every contract model."""
    schema = app.openapi()
    schemas = schema["components"]["schemas"]

    required_models = [
        "Recommendation",
        "Explanation",
        "NextStepResponse",
        "AttemptIn",
        "AttemptResult",
        "LearnerState",
        "StateDelta",
        "ExplanationEventIn",
        "ExplanationFeedbackSummary",
        "Concept",
        "ConceptEdge",
        "PublicItem",
    ]

    for model_name in required_models:
        assert model_name in schemas, f"Missing {model_name} in OpenAPI schemas"
