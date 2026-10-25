"""Adversarial tests: what a curious or hostile real user would try against the API.

Each test names the attack. Every failure response must be a clean JSON error (never a 500, never a
stack trace), and no attack may read or change another learner's data, the study arm balance, or
the learner model.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token
from app.config import settings
from app.db import models as m
from app.telemetry.analyzer import MAX_DWELL_MS
from tests.api_helpers import API, admin, learner, register

LEARNER_ROUTES = [
    ("get", "/onboarding/questionnaire"),
    ("post", "/session/next"),
    ("get", "/learners/me/state"),
    ("get", "/learners/me/history"),
    ("get", "/tests/pretest"),
]


def assert_clean_error(r, status: int, code: str | None = None) -> None:
    assert r.status_code == status, r.text
    body = r.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message"}
    assert "Traceback" not in r.text and "sqlalchemy" not in r.text.lower()
    if code:
        assert body["error"]["code"] == code


# --- authentication -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "header",
    [
        None,
        "Bearer",
        "Bearer ",
        "Basic dXNlcjpwYXNz",
        "Bearer not-a-jwt",
        "Bearer a.b.c",
        "bearer " + "x" * 5000,
    ],
)
def test_missing_or_garbage_tokens_are_rejected(client: TestClient, header) -> None:
    headers = {"Authorization": header} if header is not None else {}
    assert_clean_error(client.get(f"{API}/auth/me", headers=headers), 401)


def test_forged_tokens_are_rejected(client: TestClient) -> None:
    victim = register(client)
    now = datetime.now(UTC)
    claims = {"sub": str(victim.id), "iat": now.timestamp(), "exp": now + timedelta(hours=1)}
    forged = [
        jwt.encode(claims, "guessed-secret-guessed-secret-guessed", algorithm="HS256"),
        jwt.encode(claims, None, algorithm="none"),  # "alg: none" downgrade
        jwt.encode({**claims, "exp": now - timedelta(seconds=1)}, settings.jwt_secret, "HS256"),
        jwt.encode({"sub": str(victim.id)}, settings.jwt_secret, "HS256"),  # no exp/iat
        jwt.encode({**claims, "sub": "not-a-uuid"}, settings.jwt_secret, "HS256"),
        jwt.encode({**claims, "sub": str(uuid.uuid4())}, settings.jwt_secret, "HS256"),
        victim.token[:-3] + ("AAA" if not victim.token.endswith("AAA") else "BBB"),  # tampered
    ]
    for token in forged:
        r = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert_clean_error(r, 401)


def test_logout_revokes_existing_tokens(client: TestClient) -> None:
    who = register(client)
    old = who.headers
    assert who.post("/auth/logout").status_code == 204
    assert_clean_error(client.get(f"{API}/auth/me", headers=old), 401)
    again = client.post(f"{API}/auth/login", json={"email": who.email, "password": who.password})
    new = {"Authorization": f"Bearer {again.json()['token']}"}
    assert client.get(f"{API}/auth/me", headers=new).status_code == 200


def test_login_does_not_reveal_which_emails_exist(client: TestClient) -> None:
    who = register(client)
    unknown = client.post(
        f"{API}/auth/login", json={"email": "nobody@example.com", "password": "whatever-1"}
    )
    wrong = client.post(f"{API}/auth/login", json={"email": who.email, "password": "wrong-pass-1"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_password_guessing_is_locked_out(client: TestClient) -> None:
    who = register(client)
    other = register(client)
    for _ in range(settings.login_max_failures):
        r = client.post(f"{API}/auth/login", json={"email": who.email, "password": "guess-123"})
        assert r.status_code == 401
    locked = client.post(f"{API}/auth/login", json={"email": who.email, "password": who.password})
    assert_clean_error(locked, 429, "TOO_MANY_LOGIN_ATTEMPTS")
    assert int(locked.headers["Retry-After"]) > 0
    # the lock is per account: someone else on the same network can still log in
    ok = client.post(f"{API}/auth/login", json={"email": other.email, "password": other.password})
    assert ok.status_code == 200


def test_credential_stuffing_from_one_client_is_locked_out(client: TestClient) -> None:
    attempts = settings.login_max_failures * 5
    for i in range(attempts):
        client.post(
            f"{API}/auth/login", json={"email": f"v{i}@example.com", "password": "pw-12345"}
        )
    r = client.post(
        f"{API}/auth/login", json={"email": "v-new@example.com", "password": "pw-12345"}
    )
    assert_clean_error(r, 429, "TOO_MANY_LOGIN_ATTEMPTS")


@pytest.mark.parametrize(
    "body",
    [
        {"email": "a@example.com", "password": "short", "display_name": "x"},
        {"email": "a@example.com", "password": "a" * 73, "display_name": "x"},  # bcrypt limit
        {"email": "a@example.com", "password": "é" * 40, "display_name": "x"},  # 80 bytes
        {"email": "a@example.com", "password": "aaaaaaaa", "display_name": "x"},  # too simple
        {"email": "a@example.com", "password": "pass\x00word-1", "display_name": "x"},
        {"email": "not-an-email", "password": "Good-pass-1", "display_name": "x"},
        {"email": "a@example.com", "password": "Good-pass-1", "display_name": "   "},
        {"email": "a@example.com", "password": "Good-pass-1", "display_name": "a\x00b"},
        {"email": "a@example.com", "password": "Good-pass-1", "display_name": "x" * 101},
        {"email": "a@example.com", "password": "Good-pass-1"},
        {"email": "a@example.com", "password": 12345678, "display_name": "x"},
    ],
)
def test_bad_registrations_are_rejected_cleanly(client: TestClient, body: dict) -> None:
    assert_clean_error(client.post(f"{API}/auth/register", json=body), 422)


def test_mass_assignment_cannot_make_an_admin_or_pick_an_arm(client: TestClient, db) -> None:
    body = {"email": "sneaky@example.com", "password": "Good-pass-1", "display_name": "S"}
    for extra in ({"is_admin": True}, {"arm": "closed_loop"}, {"consent_at": "2026-01-01"}):
        assert_clean_error(client.post(f"{API}/auth/register", json=body | extra), 422)
    assert db.scalar(select(func.count()).select_from(m.User)) == 0


def test_html_in_display_name_is_stored_as_text(client: TestClient) -> None:
    r = client.post(
        f"{API}/auth/register",
        json={
            "email": "xss@example.com",
            "password": "Good-pass-1",
            "display_name": "<script>alert(1)</script>",
        },
    )
    assert r.status_code == 201
    assert r.json()["user"]["display_name"] == "<script>alert(1)</script>"
    assert r.headers["content-type"].startswith("application/json")  # never rendered as HTML


def test_every_learning_route_needs_login_and_consent(client: TestClient) -> None:
    who = register(client)  # logged in, no consent
    for method, path in LEARNER_ROUTES:
        assert_clean_error(getattr(client, method)(API + path), 401)
        assert_clean_error(getattr(who, method)(path), 403, "CONSENT_REQUIRED")


def test_withdrawn_account_cannot_act(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    who.next()
    assert who.delete("/me").status_code == 204
    for method, path in LEARNER_ROUTES:
        assert_clean_error(getattr(who, method)(path), 401)
    assert_clean_error(who.answer(), 401)


# --- authorisation: other learners' data (IDOR) -------------------------------------------------


def test_cannot_touch_another_learners_explanations_or_recommendations(
    client: TestClient, db: Session
) -> None:
    alice = learner(client, db)
    mallory = learner(client, db)
    step = alice.next()
    rec_id, ex_id = step["recommendation"]["id"], step["explanation"]["id"]

    assert_clean_error(mallory.get(f"/explanations/{ex_id}"), 404, "EXPLANATION_NOT_FOUND")
    assert_clean_error(mallory.get(f"/recommendations/{rec_id}/why"), 404)
    assert_clean_error(mallory.events(ex_id, ("clarity_rated", 0, {"rating": 1})), 404)
    assert_clean_error(mallory.post(f"/explanations/{ex_id}/close"), 404)
    assert_clean_error(mallory.answer(step=step), 404, "RECOMMENDATION_NOT_FOUND")
    # unknown ids look exactly like other people's ids
    assert (
        mallory.get(f"/explanations/{uuid.uuid4()}").json()
        == mallory.get(f"/explanations/{ex_id}").json()
    )

    # nothing of Alice's changed
    assert db.scalar(select(func.count()).select_from(m.ExplanationEventRow)) == 0
    assert db.scalar(select(func.count()).select_from(m.AttemptRow)) == 0
    assert alice.answer().status_code == 200


def test_cannot_attach_my_answer_to_someone_elses_explanation(
    client: TestClient, db: Session
) -> None:
    alice, mallory = learner(client, db), learner(client, db)
    alice_step, mine = alice.next(), mallory.next()
    r = mallory.answer(step=mine, explanation_id=alice_step["explanation"]["id"])
    assert_clean_error(r, 404, "EXPLANATION_NOT_FOUND")


def test_learners_cannot_reach_admin_or_ops(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    for path in ("/admin/metrics", "/admin/export.csv?table=users", "/ops/status"):
        assert_clean_error(who.get(path), 403, "FORBIDDEN")
        assert_clean_error(client.get(API + path), 401)


def test_export_without_salt_is_refused(client: TestClient, db: Session, monkeypatch) -> None:
    boss = admin(client, db)
    monkeypatch.setattr(settings, "analysis_salt", "")
    assert_clean_error(boss.get("/admin/export.csv"), 503, "EXPORT_DISABLED")


def test_export_cells_cannot_inject_spreadsheet_formulas(client: TestClient, db: Session) -> None:
    from app.api.admin import _cell

    assert _cell("=HYPERLINK(1)") == "'=HYPERLINK(1)" and _cell("+1") == "'+1"
    assert _cell("@SUM(A1)") == "'@SUM(A1)" and _cell("loops") == "loops"


# --- the learning loop cannot be gamed ------------------------------------------------------------


def test_answers_are_never_sent_before_answering(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    raw = who.post("/session/next").text
    assert '"answer"' not in raw and "correct" not in raw
    tests = who.get("/tests/pretest").text
    assert '"answer"' not in tests and "right" in tests  # options yes, the key no


def test_option_order_does_not_leak_the_answer(client: TestClient, db: Session) -> None:
    firsts = set()
    for _ in range(12):
        step = learner(client, db).next()
        if step["item"]["id"] == "t-vars-mcq":
            firsts.add(step["item"]["options"][0])
    assert len(firsts) > 1  # the correct option ("1") is not always first


def test_replaying_an_answer_is_rejected(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    step = who.next()
    assert who.answer().status_code == 200
    assert_clean_error(who.answer(step=step), 409, "ALREADY_ANSWERED")
    attempts = db.scalar(select(func.count()).select_from(m.AttemptRow))
    assert attempts == 1


def test_cannot_answer_a_question_that_was_not_recommended(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    step = who.next()
    for item_id in ("t-loops-short", "t-draft", "pretest-1", "no-such-item", "' OR 1=1 --"):
        if item_id == step["item"]["id"]:
            continue
        r = who.post(
            "/attempts",
            {
                "item_id": item_id,
                "response": "x",
                "latency_ms": 1,
                "recommendation_id": step["recommendation"]["id"],
            },
        )
        assert_clean_error(r, 422, "ITEM_MISMATCH")
    no_rec = {"item_id": step["item"]["id"], "response": "x", "latency_ms": 1}
    assert_clean_error(who.post("/attempts", no_rec), 422)


def test_mcq_answer_must_be_one_of_the_options(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    step = who.next()
    while step["item"]["kind"] != "mcq":
        who.answer()
        step = who.next()
    assert_clean_error(who.answer("definitely not an option"), 422, "INVALID_OPTION")


@pytest.mark.parametrize(
    "extra",
    [
        {"latency_ms": -1},
        {"latency_ms": 10**12},
        {"hints_used": -3},
        {"confidence": 9},
        {"response": "x" * 2001},
        {"response": "nul\x00byte"},
        {"recommendation_id": "not-a-uuid"},
        {"correct": True},  # the client cannot grade itself
        {"user_id": str(uuid.uuid4())},  # nor answer as someone else
    ],
)
def test_malformed_answers_are_rejected(client: TestClient, db: Session, extra: dict) -> None:
    who = learner(client, db)
    who.next()
    assert_clean_error(who.answer(**extra), 422)


def test_skipping_by_asking_again_returns_the_same_question(
    client: TestClient, db: Session
) -> None:
    who = learner(client, db)
    ids = {who.next()["recommendation"]["id"] for _ in range(5)}
    assert len(ids) == 1
    assert db.scalar(select(func.count()).select_from(m.RecommendationRow)) == 1


def test_client_cannot_claim_a_correct_followup(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    ex = who.next()["explanation"]["id"]
    r = who.events(ex, ("followup_answered", 0, {"correct": True, "item_id": "t-loops-mcq"}))
    assert_clean_error(r, 422)


@pytest.mark.parametrize(
    "event",
    [
        ("clarity_rated", 0, {"rating": 0}),
        ("clarity_rated", 0, {"rating": 6}),
        ("clarity_rated", 0, {"rating": "5"}),
        ("clarity_rated", 0, {"rating": True}),
        ("clarity_rated", 0, {}),
        ("why_rated", 0, {"helpful": "yes"}),
        ("shown", 0, {"nested": {"a": 1}}),
        ("shown", 0, {"list": [1, 2]}),
        ("shown", 0, {"k": "x" * 201}),
        ("shown", 0, {f"k{i}": i for i in range(9)}),
        ("shown", 0, {"k": "nul\x00"}),
        ("teleported", 0, {}),
    ],
)
def test_malformed_events_are_rejected(client: TestClient, db: Session, event) -> None:
    who = learner(client, db)
    ex = who.next()["explanation"]["id"]
    assert_clean_error(who.events(ex, event), 422)


def test_event_batches_are_bounded_and_deduplicated(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    ex = who.next()["explanation"]["id"]
    assert_clean_error(who.events(ex, *[("expanded", 0, {})] * 101), 422)
    assert_clean_error(who.post(f"/explanations/{ex}/events", {"events": []}), 422)
    key = str(uuid.uuid4())
    event = {"idempotency_key": key, "type": "expanded", "client_ts": datetime.now(UTC).isoformat()}
    batch = {"events": [event, event]}
    assert who.post(f"/explanations/{ex}/events", batch).json() == {"accepted": 1, "duplicates": 1}
    assert who.post(f"/explanations/{ex}/events", batch).json() == {"accepted": 0, "duplicates": 2}


def test_reusing_someone_elses_event_key_does_not_touch_their_data(
    client: TestClient, db: Session
) -> None:
    alice, mallory = learner(client, db), learner(client, db)
    a_ex, m_ex = alice.next()["explanation"]["id"], mallory.next()["explanation"]["id"]
    key = str(uuid.uuid4())
    event = {"idempotency_key": key, "type": "expanded", "client_ts": datetime.now(UTC).isoformat()}
    alice.post(f"/explanations/{a_ex}/events", {"events": [event]})
    r = mallory.post(f"/explanations/{m_ex}/events", {"events": [event | {"type": "dismissed"}]})
    assert r.json() == {"accepted": 0, "duplicates": 1}
    row = db.scalar(
        select(m.ExplanationEventRow).where(m.ExplanationEventRow.idempotency_key == key)
    )
    assert str(row.explanation_id) == a_ex and row.type == "expanded"


def test_forged_timestamps_cannot_inflate_dwell_time(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    ex = who.next()["explanation"]["id"]
    who.events(ex, ("shown", 0, {}), ("hidden", 30 * 24 * 3600, {}))  # "read it for a month"
    summary = who.post(f"/explanations/{ex}/close").json()
    assert summary["effective_dwell_ms"] <= MAX_DWELL_MS


def test_questionnaire_cannot_be_gamed(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    items = who.get("/onboarding/questionnaire").json()
    full = {i["id"]: 3 for i in items}
    bad = [
        {k: v for k, v in list(full.items())[:-1]},  # incomplete
        full | {items[0]["id"]: 6},
        full | {items[0]["id"]: 0},
        full | {"made-up-item": 3},
        full | {items[0]["id"]: "3"},
    ]
    for answers in bad:
        r = who.post("/onboarding/questionnaire", {"answers": answers})
        assert r.status_code == 422, r.text
    first = who.post("/onboarding/questionnaire", {"answers": full}).json()
    second = who.post("/onboarding/questionnaire", {"answers": {k: 5 for k in full}}).json()
    assert first == second  # a retake cannot rewrite the starting traits


def test_tests_cannot_be_retaken_or_reveal_scores(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    assert_clean_error(who.post("/tests/finaltest", {"answers": {"x": "y"}}), 422)
    assert_clean_error(who.post("/tests/pretest", {"answers": {"posttest-1": "right"}}), 422)
    assert_clean_error(who.post("/tests/pretest", {"answers": {"t-loops-mcq": "3"}}), 422)
    assert_clean_error(who.post("/tests/pretest", {"answers": {}}), 422)
    assert who.post("/tests/pretest", {"answers": {"pretest-1": "right"}}).status_code == 201
    assert_clean_error(who.post("/tests/pretest", {"answers": {"pretest-1": "right"}}), 409)


# --- robustness: malformed input never breaks the server -----------------------------------------


def test_malformed_requests_get_clean_errors(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    headers = who.headers | {"Content-Type": "application/json"}
    for body in ("{", "null", "[]", '"text"', "{'single': 'quotes'}", "\x00"):
        r = client.post(f"{API}/attempts", content=body, headers=headers)
        assert_clean_error(r, 422)
    for path in ("/explanations/not-a-uuid", "/recommendations/1/why", "/tests/../admin"):
        r = who.get(path)
        assert r.status_code in (404, 422) and "Traceback" not in r.text
    for params in ({"limit": 0}, {"limit": 10_000}, {"before_id": -1}, {"limit": "many"}):
        assert_clean_error(who.get("/learners/me/history", params=params), 422)


@pytest.mark.parametrize(
    "subject",
    ["' OR '1'='1", "loops; DROP TABLE users;--", "../../etc/passwd", "x" * 101, "\x00", "%00"],
)
def test_injection_strings_in_queries_are_inert(client: TestClient, db: Session, subject) -> None:
    who = learner(client, db)
    r = who.get("/learners/me/explain", params={"subject": subject})
    assert r.status_code in (404, 422) and "Traceback" not in r.text
    assert db.scalar(select(func.count()).select_from(m.User)) == 1


def test_oversized_bodies_are_refused(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    huge = json.dumps({"answers": {f"k{i}": "x" * 100 for i in range(1000)}})
    r = client.post(
        f"{API}/tests/pretest",
        content=huge,
        headers=who.headers | {"Content-Type": "application/json"},
    )
    assert_clean_error(r, 413, "PAYLOAD_TOO_LARGE")


def test_fuzzed_bodies_never_cause_server_errors(client: TestClient, db: Session) -> None:
    import random

    rng = random.Random(1)
    who = learner(client, db)
    step = who.next()
    values = [None, True, -1, 0, 2**63, 1.5, float("1e308"), "", "x" * 300, [], {}, ["a"], {"a": 1}]
    values += [step["recommendation"]["id"], step["item"]["id"], str(uuid.uuid4()), "‮\U0001f600"]
    routes = {
        "/attempts": ["item_id", "response", "latency_ms", "recommendation_id", "explanation_id"],
        f"/explanations/{step['explanation']['id']}/events": ["events"],
        "/onboarding/questionnaire": ["answers"],
        "/tests/pretest": ["answers"],
        "/auth/consent": ["anything"],
    }
    for _ in range(150):
        path, fields = rng.choice(list(routes.items()))
        body = {f: rng.choice(values) for f in rng.sample(fields, rng.randint(0, len(fields)))}
        r = who.post(path, body)
        assert r.status_code < 500, (path, body, r.text)


# --- transport-level protections -----------------------------------------------------------------


def test_security_headers_and_no_caching_of_personal_data(client: TestClient, db: Session) -> None:
    who = learner(client, db)
    r = who.get("/learners/me/state")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Cache-Control"] == "no-store"


def test_cors_allows_only_the_configured_frontend(client: TestClient) -> None:
    ok = client.options(
        f"{API}/auth/login",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    evil = client.options(
        f"{API}/auth/login",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in evil.headers


def test_spoofed_forwarded_for_does_not_bypass_rate_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 3)
    codes = [
        client.get(f"{API}/graph", headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code
        for i in range(5)
    ]
    assert codes[-1] == 429


def test_tokens_for_admin_need_the_admin_flag_not_just_a_valid_signature(
    client: TestClient, db: Session
) -> None:
    who = learner(client, db)
    token = create_access_token(who.id)  # perfectly valid token, ordinary account
    r = client.get(f"{API}/admin/metrics", headers={"Authorization": f"Bearer {token}"})
    assert_clean_error(r, 403)
