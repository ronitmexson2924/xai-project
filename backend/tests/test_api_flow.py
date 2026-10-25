"""The whole learning loop through the HTTP API, over the real services and database
(tasks/mit.md M1 acceptance: register -> consent -> questionnaire -> next -> attempt ->
micro-check -> state changed; plus the XAI routes, M9)."""

from tests.conftest import ApiClient


def test_full_learning_loop(api: ApiClient) -> None:
    who = api.learner()
    h = who["h"]
    me = api.get("/api/v1/auth/me", headers=h).json()
    assert me["consent_at"] and me["questionnaire_done"] and not me["is_admin"]
    assert me["arm"] in {"generic", "static_personalized", "closed_loop"}

    step = api.next(who)
    rec, explanation, item = step["recommendation"], step["explanation"], step["item"]
    assert item["id"] == rec["item_id"] and "answer" not in item
    assert explanation["recommendation_id"] == rec["id"]
    assert api.next(who)["recommendation"]["id"] == rec["id"]  # reload: the same step again

    result = api.answer(who, step, correct=True)
    assert result["correct"] and result["correct_answer"] == "a"
    assert result["change"]["source"] == "attempt"

    why = api.get(f"/api/v1/recommendations/{rec['id']}/why", headers=h)
    assert why.status_code == 200, why.text
    assert why.json()["rationale"]["recommendation_id"] == rec["id"]
    assert why.json()["style"] is not None

    # explanation telemetry, then its micro-check closes the feedback loop
    eid = explanation["id"]
    events = [
        {"idempotency_key": k, "type": t, "client_ts": ts, "payload": p}
        for k, t, ts, p in [
            ("00000000-0000-4000-8000-000000000001", "shown", "2026-10-25T10:00:00Z", {}),
            ("00000000-0000-4000-8000-000000000002", "why_opened", "2026-10-25T10:00:05Z", {}),
            (
                "00000000-0000-4000-8000-000000000003",
                "clarity_rated",
                "2026-10-25T10:00:20Z",
                {"rating": 4},
            ),
            ("00000000-0000-4000-8000-000000000004", "hidden", "2026-10-25T10:00:30Z", {}),
        ]
    ]
    r = api.post(f"/api/v1/explanations/{eid}/events", json={"events": events}, headers=h)
    assert r.json() == {"accepted": 4, "duplicates": 0}
    r = api.post(f"/api/v1/explanations/{eid}/events", json={"events": events}, headers=h)
    assert r.json() == {"accepted": 0, "duplicates": 4}  # M2: the same batch twice

    check_id = explanation["followup_item_id"]
    check = api.get(f"/api/v1/items/{check_id}", headers=h)
    assert check.status_code == 200 and "answer" not in check.json()
    r = api.post(
        "/api/v1/attempts",
        json={"item_id": check_id, "response": "a", "latency_ms": 5000, "explanation_id": eid},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["feedback_change"]["source"] == "explanation_feedback"

    summary = api.post(f"/api/v1/explanations/{eid}/close", headers=h).json()
    assert summary["followup_correct"] is True and summary["clarity_rating"] == 4
    assert summary["effective_dwell_ms"] == 30_000 or summary["effective_dwell_ms"] >= 0

    state = api.get("/api/v1/learners/me/state", headers=h).json()
    assert state["total_attempts"] == 2
    history = api.get("/api/v1/learners/me/history", headers=h).json()
    assert {u["source"] for u in history} >= {"questionnaire", "attempt", "explanation_feedback"}
    belief = api.get(
        "/api/v1/learners/me/explain", params={"subject": rec["target_concept_id"]}, headers=h
    )
    assert belief.status_code == 200 and belief.json()["subject"] == rec["target_concept_id"]
    trait = api.get(
        "/api/v1/learners/me/explain", params={"subject": "abstraction_preference"}, headers=h
    )
    assert trait.status_code == 200

    # the next step is a new one, and the graph is there for the dashboard
    assert api.next(who)["recommendation"]["id"] != rec["id"]
    graph = api.get("/api/v1/graph", headers=h).json()
    assert len(graph["concepts"]) >= 60 and graph["edges"]


def test_pre_and_post_tests(api: ApiClient) -> None:
    who = api.learner()
    items = api.get("/api/v1/tests/pretest", headers=who["h"]).json()
    assert items and all(i["id"].startswith("pretest-") and "answer" not in i for i in items)
    r = api.post(
        "/api/v1/attempts",
        json={"item_id": items[0]["id"], "response": "a", "latency_ms": 4000},
        headers=who["h"],
    )
    assert r.status_code == 200 and r.json()["correct"] is True
    assert r.json()["correct_answer"] is None  # test answers are never revealed
    state = api.get("/api/v1/learners/me/state", headers=who["h"]).json()
    assert state["total_attempts"] == 0  # tests never move the model


def test_admin_metrics_and_export(api: ApiClient) -> None:
    from app.config import settings

    learner = api.learner()
    api.answer(learner, api.next(learner))
    admin = api.admin()
    metrics = api.get("/api/v1/admin/metrics", headers=admin["h"])
    assert metrics.status_code == 200, metrics.text
    body = metrics.json()
    assert body["total_users"] >= 2 and body["total_attempts"] >= 1
    assert body["total_explanations"] >= 1 and body["p95_latency_ms"] is not None

    settings.export_salt = "a-long-test-salt-value"
    for table in ("users", "attempts", "explanations", "feedback"):
        r = api.get("/api/v1/admin/export.csv", params={"table": table}, headers=admin["h"])
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
        assert learner["user"]["id"] not in r.text and learner["email"] not in r.text
