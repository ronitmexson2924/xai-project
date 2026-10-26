"""The HTTP API end to end on Postgres (M1, M6, M7, M9), as a learner's browser drives it.

Replaces the earlier in-memory API tests (test_api_m1, test_auth, test_dashboards), which tested
the fakes the API used before it was wired to the real services.
"""

from collections import Counter

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from tests.api_helpers import API, admin, learner, register


def test_register_login_me_and_consent(client: TestClient) -> None:
    who = register(client, "Mixed.Case@Example.com")
    assert who.email == "Mixed.Case@Example.com"
    me = who.get("/auth/me").json()
    assert me["email"] == "mixed.case@example.com" and me["consent_at"] is None
    assert me["is_admin"] is False

    assert who.post("/session/next").json()["error"]["code"] == "CONSENT_REQUIRED"
    first = who.post("/auth/consent").json()["consent_at"]
    assert who.post("/auth/consent").json()["consent_at"] == first  # recorded once

    login = client.post(
        f"{API}/auth/login", json={"email": "mixed.case@example.com", "password": who.password}
    )
    assert login.status_code == 200 and login.json()["user"]["id"] == str(who.id)
    assert (
        client.post(
            f"{API}/auth/register",
            json={
                "email": "MIXED.case@example.com",
                "password": "Another-pass-1",
                "display_name": "x",
            },
        ).json()["error"]["code"]
        == "USER_ALREADY_EXISTS"
    )


def test_arms_are_balanced(client: TestClient) -> None:
    arms = Counter(register(client).arm for _ in range(9))
    assert arms == {"generic": 3, "static_personalized": 3, "closed_loop": 3}


def test_full_learning_loop(client: TestClient, db: Session) -> None:
    ada = learner(client, db, "closed_loop")
    assert ada.get("/auth/me").json()["onboarded"] is False
    delta = ada.questionnaire(5)
    assert ada.get("/auth/me").json()["onboarded"] is True
    login = client.post(f"{API}/auth/login", json={"email": ada.email, "password": ada.password})
    assert login.json()["user"]["onboarded"] is True
    assert delta["source"] == "questionnaire"
    assert ada.questionnaire(1) == delta  # taken once: a second submission changes nothing

    for _ in range(4):
        step = ada.next()
        rec, explanation, item = step["recommendation"], step["explanation"], step["item"]
        assert "answer" not in item
        assert explanation["followup_item_id"] == item["id"] == rec["item_id"]
        assert ada.next()["recommendation"]["id"] == rec["id"]  # pending one is served again

        why = ada.get(f"/recommendations/{rec['id']}/why").json()
        assert why["rationale"]["recommendation_id"] == rec["id"] and why["rationale"]["summary"]
        assert why["style"]["source"] == explanation["style_source"]

        assert ada.events(
            explanation["id"], ("shown", 0, {}), ("clarity_rated", 20, {"rating": 4})
        ).json() == {"accepted": 2, "duplicates": 0}
        result = ada.answer()
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["delta"]["source"] == "attempt" and body["change"]["source"] == "attempt"
        # "Continue" closes the explanation (placement answers are not its micro-check)
        assert ada.post(f"/explanations/{explanation['id']}/close").status_code == 200

    state = ada.get("/learners/me/state").json()
    assert state["total_attempts"] == 4
    history = ada.get("/learners/me/history").json()
    assert {h["source"] for h in history} == {"questionnaire", "attempt", "explanation_feedback"}
    assert [h["id"] for h in history] == sorted((h["id"] for h in history), reverse=True)
    page = ada.get("/learners/me/history", params={"limit": 2}).json()
    older = ada.get("/learners/me/history", params={"before_id": page[-1]["id"]}).json()
    assert len(page) == 2 and all(h["id"] < page[-1]["id"] for h in older)

    feedback = db.scalar(select(func.count()).select_from(m.ExplanationFeedbackRow))
    assert feedback == 4  # every answered micro-check closed its explanation's feedback loop
    belief = ada.get("/learners/me/explain", params={"subject": "loops"}).json()
    assert belief["subject"] == "loops" and belief["summary"]
    trait = ada.get("/learners/me/explain", params={"subject": "depth_preference"}).json()
    assert trait["label"] and 0 <= trait["value"] <= 1


def test_style_follows_the_learners_arm(client: TestClient, db: Session) -> None:
    sources = {}
    for arm in ("generic", "static_personalized", "closed_loop"):
        who = learner(client, db, arm)
        who.questionnaire(5)
        sources[arm] = who.next()["explanation"]["style_source"]
    assert sources["generic"] == "generic"
    assert sources["static_personalized"] == "trait_mapped"
    assert sources["closed_loop"] in ("thompson", "exploration")


def test_placement_answers_do_not_score_an_unseen_explanation(
    client: TestClient, db: Session
) -> None:
    who = learner(client, db)
    step = who.next()
    assert step["recommendation"]["kind"] == "diagnostic_item"
    who.answer()
    assert db.scalar(select(func.count()).select_from(m.ExplanationFeedbackRow)) == 0
    summary = who.post(f"/explanations/{step['explanation']['id']}/close").json()
    assert summary["followup_correct"] is None  # the answer came before the explanation


def test_close_without_answer_is_idempotent(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    explanation_id = who.next()["explanation"]["id"]
    who.events(explanation_id, ("shown", 0, {}), ("dismissed", 1, {}))
    first = who.post(f"/explanations/{explanation_id}/close").json()
    assert (
        first["dismissed_quickly"] is True and first["change"]["source"] == "explanation_feedback"
    )
    again = who.post(f"/explanations/{explanation_id}/close").json()
    assert again["explanation_id"] == explanation_id and again["change"] is None
    assert who.get(f"/explanations/{explanation_id}").json()["id"] == explanation_id


def test_graph_questionnaire_and_draft_items_hidden(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    graph = who.get("/graph").json()
    assert len(graph["concepts"]) >= 50 and graph["edges"]
    items = who.get("/onboarding/questionnaire").json()
    assert len(items) == 20 and {"id", "trait", "text"} <= set(items[0])
    served = {who.next()["item"]["id"]}
    for _ in range(5):
        who.answer()
        served.add(who.next()["item"]["id"])
    assert "t-draft" not in served and not any(
        i.startswith(("pretest-", "posttest-")) for i in served
    )


def test_pre_and_post_tests(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    assert who.post("/tests/posttest", {"answers": {"posttest-1": "right"}}).status_code == 409
    test = who.get("/tests/pretest").json()
    assert [i["id"] for i in test["items"]] == ["pretest-1", "pretest-2"] and not test["submitted"]
    assert all("answer" not in i for i in test["items"])
    r = who.post("/tests/pretest", {"answers": {"pretest-1": "right"}})
    assert r.status_code == 201 and r.json() == {"phase": "pretest", "answered": 1}
    assert "correct" not in r.text  # no score, no answers
    assert who.get("/tests/pretest").json()["submitted"] is True
    assert who.post("/tests/pretest", {"answers": {"pretest-2": "right"}}).status_code == 409
    assert who.post("/tests/posttest", {"answers": {"posttest-2": "right"}}).status_code == 201

    rows = db.execute(select(m.AttemptRow.item_id, m.AttemptRow.correct)).all()
    assert sorted(rows) == [
        ("posttest-1", False),
        ("posttest-2", True),
        ("pretest-1", True),
        ("pretest-2", False),
    ]
    # tests never move the learner model
    assert db.scalar(select(func.count()).select_from(m.LearnerConceptStateRow)) == 0


def test_withdrawal_deactivates_then_purge_deletes(client: TestClient, db: Session) -> None:
    from app.auth.purge import purge_soft_deleted_users

    who = learner(client, db)
    who.next()
    who.answer()
    assert who.delete("/me").status_code == 204
    assert who.get("/auth/me").status_code == 401
    login = client.post(f"{API}/auth/login", json={"email": who.email, "password": who.password})
    assert login.status_code == 401

    assert purge_soft_deleted_users(db, retention_days=0, dry_run=True) == 1
    assert purge_soft_deleted_users(db, retention_days=0) == 1
    assert db.get(m.User, who.id) is None
    assert db.scalar(select(func.count()).select_from(m.AttemptRow)) == 0  # cascaded


def test_admin_metrics_export_and_ops(client: TestClient, db: Session) -> None:
    boss = admin(client, db)
    for arm in ("generic", "closed_loop"):
        who = learner(client, db, arm)
        who.next()
        who.events(who.last["explanation"]["id"], ("clarity_rated", 1, {"rating": 5}))
        who.answer()
        who.post(f"/explanations/{who.last['explanation']['id']}/close")

    metrics = boss.get("/admin/metrics").json()
    assert metrics["total_users"] == 2 and metrics["consented_users"] == 2  # admin not counted
    assert metrics["total_attempts"] == 2 and metrics["total_explanations"] == 2
    assert metrics["clarity_distribution"]["5"] == 2
    assert metrics["p95_explanation_latency_ms"] is not None

    users = boss.get("/admin/export.csv", params={"table": "users"})
    assert users.headers["content-type"].startswith("text/csv")
    lines = users.text.strip().splitlines()
    assert lines[0] == "pseudonym_id,created_at,consented,arm" and len(lines) == 3
    assert "@" not in users.text and str(who.id) not in users.text
    attempts = boss.get("/admin/export.csv", params={"table": "attempts"}).text
    assert len(attempts.strip().splitlines()) == 3
    assert boss.get("/admin/export.csv", params={"table": "secrets"}).status_code == 422

    ops = boss.get("/ops/status").json()
    assert ops["registered_learners"] == 2 and ops["active_learners_24h"] == 2


def test_health_and_openapi(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/health/ready").status_code in (200, 503)  # app engine, not the test db
    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/api/v1/session/next",
        "/api/v1/attempts",
        "/api/v1/recommendations/{recommendation_id}/why",
        "/api/v1/learners/me/explain",
        "/api/v1/tests/{phase}",
        "/api/v1/auth/logout",
    ):
        assert path in paths
