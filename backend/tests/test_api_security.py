"""Adversarial tests: a learner (or anyone on the internet) trying to break, cheat or snoop
through every route. Each test names the attack it tries."""

import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import func, select

from app.config import settings
from app.db import models as m
from tests.conftest import ApiClient

API = "/api/v1"


# --- authentication -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "header",
    [
        None,
        "Bearer",
        "Bearer not-a-jwt",
        "Basic dXNlcjpwYXNz",
        "Bearer " + jwt.encode({"sub": str(uuid.uuid4())}, "wrong-secret-" + "y" * 40),
    ],
)
def test_protected_routes_reject_missing_or_forged_tokens(api: ApiClient, header) -> None:
    headers = {"Authorization": header} if header else {}
    for method, path in [
        ("get", "/auth/me"),
        ("post", "/session/next"),
        ("get", "/learners/me/state"),
        ("get", "/admin/metrics"),
        ("get", "/graph"),
    ]:
        r = getattr(api, method)(API + path, headers=headers)
        assert r.status_code == 401, (path, r.text)
        assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_unsigned_alg_none_token_is_rejected(api: ApiClient) -> None:
    who = api.learner()
    now = int(time.time())
    forged = jwt.encode(
        {"sub": who["user"]["id"], "iat": now, "exp": now + 3600}, key=None, algorithm="none"
    )
    r = api.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_expired_token_is_rejected(api: ApiClient) -> None:
    who = api.learner()
    past = datetime.now(UTC) - timedelta(days=2)
    token = jwt.encode(
        {"sub": who["user"]["id"], "iat": int(past.timestamp()), "exp": int(past.timestamp()) + 60},
        settings.jwt_secret,
        algorithm="HS256",
    )
    assert (
        api.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    )


def test_login_does_not_reveal_whether_an_email_exists(api: ApiClient) -> None:
    who = api.register()
    wrong_pw = api.post(f"{API}/auth/login", json={"email": who["email"], "password": "nope-nope"})
    unknown = api.post(
        f"{API}/auth/login", json={"email": "nobody@example.com", "password": "nope-nope"}
    )
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


def test_login_is_case_insensitive_and_duplicates_are_refused(api: ApiClient) -> None:
    who = api.register(email="Mixed.Case@Example.com")
    assert who["user"]["email"] == "mixed.case@example.com"
    ok = api.post(
        f"{API}/auth/login", json={"email": "MIXED.CASE@example.com", "password": who["password"]}
    )
    assert ok.status_code == 200
    dup = api.post(
        f"{API}/auth/register",
        json={"email": "mixed.case@EXAMPLE.com", "password": "another pass 9", "display_name": "x"},
    )
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "USER_ALREADY_EXISTS"


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "password": "long enough 1", "display_name": "x"},
        {"email": "a@example.com", "password": "short", "display_name": "x"},
        {"email": "a@example.com", "password": "é" * 40, "display_name": "x"},  # > 72 bytes
        {"email": "a@example.com", "password": " padded password ", "display_name": "x"},
        {"email": "a@example.com", "password": "long enough 1", "display_name": "   "},
        {"email": "a@example.com", "password": "long enough 1", "display_name": "bad\x00name"},
        {"email": "a@example.com", "password": "long enough 1", "display_name": "x" * 101},
        {"email": "a@example.com", "password": "long enough 1"},
        {"email": "a@example.com", "password": 12345678, "display_name": "x"},
    ],
)
def test_register_rejects_bad_input(api: ApiClient, body: dict) -> None:
    r = api.post(f"{API}/auth/register", json=body)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_injection_strings_are_stored_as_plain_text(api: ApiClient) -> None:
    name = "Robert'); DROP TABLE users;-- <script>alert(1)</script>"
    r = api.post(
        f"{API}/auth/register",
        json={"email": "bobby@example.com", "password": "tables are fine 1", "display_name": name},
    )
    assert r.status_code == 201 and r.json()["user"]["display_name"] == name
    assert api.session.scalar(select(m.User).where(m.User.email == "bobby@example.com"))


def test_new_accounts_are_never_admins_and_cannot_choose_their_arm(api: ApiClient) -> None:
    r = api.post(
        f"{API}/auth/register",
        json={
            "email": "sneaky@example.com",
            "password": "let me in 123",
            "display_name": "s",
            "is_admin": True,
            "arm": "closed_loop",
        },
    )
    assert r.status_code == 201
    assert r.json()["user"]["is_admin"] is False
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert api.get(f"{API}/admin/metrics", headers=h).status_code == 403


def test_arms_stay_balanced(api: ApiClient) -> None:
    for _ in range(9):
        api.register()
    counts = dict(
        api.session.execute(
            select(m.ExperimentAssignment.arm, func.count()).group_by(m.ExperimentAssignment.arm)
        ).all()
    )
    assert len(counts) == 3 and max(counts.values()) - min(counts.values()) <= 1


# --- consent and onboarding ---------------------------------------------------------------------


def test_learning_routes_require_consent(api: ApiClient) -> None:
    who = api.register()
    for method, path in [
        ("get", "/onboarding/questionnaire"),
        ("post", "/session/next"),
        ("get", "/learners/me/state"),
        ("get", "/tests/pretest"),
    ]:
        r = getattr(api, method)(API + path, headers=who["h"])
        assert r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_REQUIRED", path


def test_consent_time_cannot_be_rewritten(api: ApiClient) -> None:
    who = api.learner(questionnaire=False)
    first = api.post(f"{API}/auth/consent", headers=who["h"]).json()["consent_at"]
    again = api.post(f"{API}/auth/consent", headers=who["h"]).json()["consent_at"]
    assert first == again


def test_questionnaire_hides_scoring_and_validates_answers(api: ApiClient) -> None:
    who = api.learner(questionnaire=False)
    items = api.get(f"{API}/onboarding/questionnaire", headers=who["h"]).json()
    assert len(items) >= 20 and all(set(i) == {"id", "text"} for i in items)
    good = {i["id"]: 3 for i in items}
    bad_answers = [
        {k: v for k, v in list(good.items())[1:]},  # one missing
        {**good, items[0]["id"]: 6},  # out of range
        {**good, items[0]["id"]: 0},
        {**good, "made-up-item": 3},  # unknown item
    ]
    for answers in bad_answers:
        r = api.post(f"{API}/onboarding/questionnaire", json={"answers": answers}, headers=who["h"])
        assert r.status_code == 422, r.text
    assert (
        api.post(
            f"{API}/onboarding/questionnaire", json={"answers": good}, headers=who["h"]
        ).status_code
        == 200
    )
    # a second submission cannot rewrite the traits
    flipped = {k: 5 for k in good}
    second = api.post(
        f"{API}/onboarding/questionnaire", json={"answers": flipped}, headers=who["h"]
    )
    assert second.status_code == 200
    rows = api.session.scalars(
        select(m.QuestionnaireResponseRow.value).where(
            m.QuestionnaireResponseRow.user_id == uuid.UUID(who["user"]["id"])
        )
    ).all()
    assert set(rows) == {3}


def test_session_needs_the_questionnaire_first(api: ApiClient) -> None:
    who = api.learner(questionnaire=False)
    r = api.post(f"{API}/session/next", headers=who["h"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "QUESTIONNAIRE_REQUIRED"


# --- answers: cheating and replay --------------------------------------------------------------


def _attempt(api: ApiClient, who: dict, **body) -> object:
    body.setdefault("latency_ms", 5000)
    return api.post(f"{API}/attempts", json=body, headers=who["h"])


def test_the_same_answer_cannot_be_submitted_twice(api: ApiClient) -> None:
    who = api.learner()
    step = api.next(who)
    api.answer(who, step, correct=False)
    again = _attempt(
        api,
        who,
        item_id=step["item"]["id"],
        response="a",
        recommendation_id=step["recommendation"]["id"],
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "ALREADY_ANSWERED"


def test_items_that_were_not_served_cannot_be_answered(api: ApiClient) -> None:
    who = api.learner()
    step = api.next(who)
    other = next(
        i.id
        for i in api.session.scalars(select(m.ItemRow))
        if not i.is_microcheck
        and i.id != step["item"]["id"]
        and not i.id.startswith(("pre", "post"))
    )
    no_link = _attempt(api, who, item_id=other, response="a")
    assert no_link.status_code == 422 and no_link.json()["error"]["code"] == "ITEM_NOT_SERVED"
    wrong_item = _attempt(
        api, who, item_id=other, response="a", recommendation_id=step["recommendation"]["id"]
    )
    assert wrong_item.status_code == 422
    unknown = _attempt(api, who, item_id="../../etc/passwd", response="a")
    assert unknown.status_code == 404
    random_rec = _attempt(
        api, who, item_id=step["item"]["id"], response="a", recommendation_id=str(uuid.uuid4())
    )
    assert random_rec.status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        {"response": "an option that does not exist"},
        {"response": ""},
        {"response": "a" * 501},
        {"latency_ms": -1},
        {"hints_used": -3},
        {"hints_used": 10_000},
        {"confidence": 9},
        {"latency_ms": "fast"},
    ],
)
def test_malformed_answers_are_rejected(api: ApiClient, change: dict) -> None:
    who = api.learner()
    step = api.next(who)
    body = {
        "item_id": step["item"]["id"],
        "response": "a",
        "latency_ms": 5000,
        "recommendation_id": step["recommendation"]["id"],
        **change,
    }
    r = api.post(f"{API}/attempts", json=body, headers=who["h"])
    assert r.status_code == 422, r.text
    # nothing was recorded, so the real answer still goes through
    api.answer(who, step)


def test_both_ids_at_once_are_rejected(api: ApiClient) -> None:
    who = api.learner()
    step = api.next(who)
    r = _attempt(
        api,
        who,
        item_id=step["item"]["id"],
        response="a",
        recommendation_id=step["recommendation"]["id"],
        explanation_id=step["explanation"]["id"],
    )
    assert r.status_code == 422


def test_huge_latency_is_clamped_not_stored(api: ApiClient) -> None:
    who = api.learner()
    step = api.next(who)
    r = _attempt(
        api,
        who,
        item_id=step["item"]["id"],
        response="a",
        latency_ms=10**12,
        recommendation_id=step["recommendation"]["id"],
    )
    assert r.status_code == 200
    stored = api.session.scalar(
        select(m.AttemptRow.latency_ms).where(
            m.AttemptRow.recommendation_id == uuid.UUID(step["recommendation"]["id"])
        )
    )
    assert stored == 60 * 60 * 1000


def test_test_items_can_be_answered_once_and_are_not_browsable(api: ApiClient) -> None:
    who = api.learner()
    item = api.get(f"{API}/tests/posttest", headers=who["h"]).json()[0]
    assert _attempt(api, who, item_id=item["id"], response="b").status_code == 200
    second = _attempt(api, who, item_id=item["id"], response="a")
    assert second.status_code == 409
    assert api.get(f"{API}/items/{item['id']}", headers=who["h"]).status_code == 404
    assert api.get(f"{API}/tests/finaltest", headers=who["h"]).status_code == 422


# --- other people's data (IDOR) -----------------------------------------------------------------


def test_one_learner_cannot_touch_anothers_data(api: ApiClient) -> None:
    alice, mallory = api.learner(), api.learner()
    step = api.next(alice)
    rec_id, exp_id = step["recommendation"]["id"], step["explanation"]["id"]
    mh = mallory["h"]
    attempts = [
        api.get(f"{API}/explanations/{exp_id}", headers=mh),
        api.post(f"{API}/explanations/{exp_id}/close", headers=mh),
        api.post(
            f"{API}/explanations/{exp_id}/events",
            json={
                "events": [
                    {
                        "idempotency_key": str(uuid.uuid4()),
                        "type": "shown",
                        "client_ts": "2026-10-25T10:00:00Z",
                    }
                ]
            },
            headers=mh,
        ),
        api.get(f"{API}/recommendations/{rec_id}/why", headers=mh),
        api.get(f"{API}/items/{step['item']['id']}", headers=mh),
        _attempt(api, mallory, item_id=step["item"]["id"], response="a", recommendation_id=rec_id),
        _attempt(
            api,
            mallory,
            item_id=step["explanation"]["followup_item_id"],
            response="a",
            explanation_id=exp_id,
        ),
    ]
    for r in attempts:
        assert r.status_code == 404, r.text
    # and Alice's step is untouched: she can still answer it
    api.answer(alice, step)


def test_ids_that_do_not_exist_look_the_same_as_other_peoples(api: ApiClient) -> None:
    who = api.learner()
    r = api.get(f"{API}/explanations/{uuid.uuid4()}", headers=who["h"])
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    assert api.get(f"{API}/explanations/not-a-uuid", headers=who["h"]).status_code == 422


# --- telemetry: forged signals -------------------------------------------------------------------


def _events(*specs) -> dict:  # noqa: ANN002
    return {
        "events": [
            {"idempotency_key": str(uuid.uuid4()), "type": t, "client_ts": ts, "payload": p}
            for t, ts, p in specs
        ]
    }


def test_forged_dwell_and_followup_events_are_not_trusted(api: ApiClient) -> None:
    who = api.learner()
    step = api.next(who)
    eid = step["explanation"]["id"]
    forged = _events(
        ("shown", "2020-01-01T00:00:00Z", {}),  # years "on the page"
        ("followup_answered", "2026-10-25T10:00:00Z", {"correct": True}),
        ("clarity_rated", "2026-10-25T10:00:01Z", {"rating": 99}),
        ("clarity_rated", "2026-10-25T10:00:02Z", {"rating": "5"}),
        ("hidden", "2030-01-01T00:00:00Z", {}),
    )
    assert (
        api.post(f"{API}/explanations/{eid}/events", json=forged, headers=who["h"]).status_code
        == 200
    )
    summary = api.post(f"{API}/explanations/{eid}/close", headers=who["h"]).json()
    assert summary["followup_correct"] is None  # only a graded attempt counts
    assert summary["clarity_rating"] is None
    assert summary["effective_dwell_ms"] <= 60_000  # bounded by real time since it was shown


def test_event_batches_are_bounded_and_typed(api: ApiClient) -> None:
    who = api.learner()
    eid = api.next(who)["explanation"]["id"]
    too_many = _events(*[("shown", "2026-10-25T10:00:00Z", {})] * 201)
    assert (
        api.post(f"{API}/explanations/{eid}/events", json=too_many, headers=who["h"]).status_code
        == 422
    )
    bad_type = _events(("hacked", "2026-10-25T10:00:00Z", {}))
    assert (
        api.post(f"{API}/explanations/{eid}/events", json=bad_type, headers=who["h"]).status_code
        == 422
    )


def test_closing_twice_does_not_apply_feedback_twice(api: ApiClient) -> None:
    who = api.learner()
    eid = api.next(who)["explanation"]["id"]
    first = api.post(f"{API}/explanations/{eid}/close", headers=who["h"])
    second = api.post(f"{API}/explanations/{eid}/close", headers=who["h"])
    assert first.status_code == second.status_code == 200
    updates = api.session.scalars(
        select(m.StateUpdateRow).where(
            m.StateUpdateRow.user_id == uuid.UUID(who["user"]["id"]),
            m.StateUpdateRow.source == "explanation_feedback",
        )
    ).all()
    assert len(updates) == 1


# --- admin ---------------------------------------------------------------------------------------


def test_admin_routes_are_for_admins_only(api: ApiClient) -> None:
    who = api.learner()
    for path in ("/admin/metrics", "/admin/export.csv?table=users"):
        r = api.get(API + path, headers=who["h"])
        assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"


def test_export_needs_a_salt_and_only_known_tables(api: ApiClient) -> None:
    admin = api.admin()
    settings.export_salt = ""
    assert api.get(f"{API}/admin/export.csv?table=users", headers=admin["h"]).status_code == 503
    settings.export_salt = "a-long-test-salt-value"
    for table in ("passwords", "users;DROP TABLE users", "../../etc"):
        r = api.get(f"{API}/admin/export.csv", params={"table": table}, headers=admin["h"])
        assert r.status_code == 422


def test_export_neutralises_spreadsheet_formulas(api: ApiClient) -> None:
    from app.api.admin import _cell

    assert _cell('=HYPERLINK("http://evil")').startswith("'")
    assert _cell("+1") == "'+1" and _cell("@cmd") == "'@cmd" and _cell("plain") == "plain"


# --- account deletion ----------------------------------------------------------------------------


def test_deleted_accounts_stop_working_and_lose_their_pii(api: ApiClient) -> None:
    who = api.learner()
    api.answer(who, api.next(who))
    assert api.delete(f"{API}/me", headers=who["h"]).status_code == 204
    assert api.get(f"{API}/auth/me", headers=who["h"]).status_code == 401
    login = api.post(f"{API}/auth/login", json={"email": who["email"], "password": who["password"]})
    assert login.status_code == 401
    user = api.session.get(m.User, uuid.UUID(who["user"]["id"]))
    assert who["email"] not in user.email and user.display_name == "deleted"
    # the address can be used again for a fresh account
    assert api.register(email=who["email"])["user"]["id"] != who["user"]["id"]


def test_purge_removes_deleted_accounts_and_their_data(api: ApiClient) -> None:
    from app.auth.purge import purge_deleted_users

    who = api.learner()
    api.answer(who, api.next(who))
    api.delete(f"{API}/me", headers=who["h"])
    user_id = uuid.UUID(who["user"]["id"])
    assert purge_deleted_users(api.session, retention_days=1) == 0  # still within retention
    assert purge_deleted_users(api.session, retention_days=0) >= 1
    assert api.session.get(m.User, user_id) is None
    assert not api.session.scalars(
        select(m.AttemptRow).where(m.AttemptRow.user_id == user_id)
    ).all()


# --- abuse limits, headers, errors ---------------------------------------------------------------


def test_login_guessing_is_rate_limited(api: ApiClient) -> None:
    who = api.register()
    settings.rate_limit_enabled = True
    codes = [
        api.post(
            f"{API}/auth/login", json={"email": who["email"], "password": f"guess-{i}xx"}
        ).status_code
        for i in range(settings.auth_rate_limit_per_minute + 2)
    ]
    assert codes[0] == 401 and codes[-1] == 429
    blocked = api.post(
        f"{API}/auth/login", json={"email": who["email"], "password": who["password"]}
    )
    assert blocked.status_code == 429 and "Retry-After" in blocked.headers


def test_spoofed_forwarded_for_does_not_bypass_rate_limits(api: ApiClient) -> None:
    settings.rate_limit_enabled = True
    old = settings.rate_limit_requests_per_minute
    settings.rate_limit_requests_per_minute = 5
    try:
        codes = [
            api.get(f"{API}/graph", headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code
            for i in range(8)
        ]
    finally:
        settings.rate_limit_requests_per_minute = old
    assert codes.count(429) >= 3


def test_oversized_bodies_are_refused(api: ApiClient) -> None:
    r = api.post(
        f"{API}/auth/login",
        content=b'{"email": "' + b"a" * 300_000 + b'@x.com", "password": "x"}',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 413


def test_malformed_json_gets_the_uniform_error(api: ApiClient) -> None:
    r = api.post(
        f"{API}/auth/login", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_security_headers_and_cors(api: ApiClient) -> None:
    r = api.get("/health", headers={"Origin": "https://evil.example"})
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "access-control-allow-origin" not in r.headers
    ok = api.get("/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_belief_subject_is_validated(api: ApiClient) -> None:
    who = api.learner()
    for subject in ("'; DROP TABLE users;--", "../secrets", "x" * 200):
        r = api.get(f"{API}/learners/me/explain", params={"subject": subject}, headers=who["h"])
        assert r.status_code == 422
    r = api.get(
        f"{API}/learners/me/explain", params={"subject": "no-such-concept"}, headers=who["h"]
    )
    assert r.status_code == 404


def test_production_refuses_unsafe_settings() -> None:
    from app.config import Settings

    unsafe = Settings(environment="production", jwt_secret="change-me", cors_origins="*")
    problems = unsafe.production_problems()
    assert any("JWT_SECRET" in p for p in problems) and any("CORS" in p for p in problems)
    safe = Settings(
        environment="production", jwt_secret="z" * 48, cors_origins="https://app.example"
    )
    assert safe.production_problems() == []


def test_hosted_database_urls_get_the_driver(api: ApiClient) -> None:
    from app.config import Settings

    url = Settings(database_url="postgres://u:p@host:5432/db").database_url
    assert url == "postgresql+psycopg://u:p@host:5432/db"


def test_internal_errors_do_not_leak_details(api: ApiClient, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    who = api.learner()

    def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("secret connection string postgres://admin:hunter2@db")

    monkeypatch.setattr("app.api.learners.select", boom)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(f"{API}/learners/me/history", headers=who["h"])
    assert r.status_code == 500
    assert "hunter2" not in r.text and r.json()["error"]["code"] == "INTERNAL_ERROR"
