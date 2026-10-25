from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.auth import auth_store, require_consent
from app.auth.models import ALL_ARMS, UserResponse
from app.main import app


# Add a test-only route guarded by require_consent to verify consent checking
@app.get("/api/v1/test/guarded-learning-route")
def guarded_route(user: Annotated[UserResponse, Depends(require_consent)]) -> dict[str, str]:
    return {"status": "authorized", "user_id": str(user.id)}


@pytest.fixture(autouse=True)
def clean_store() -> None:
    auth_store.clear()


def test_register_and_login() -> None:
    client = TestClient(app)

    # 1. Register
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "learner@example.com",
            "password": "secretpassword123",
            "display_name": "Ada Lovelace",
        },
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert "token" in reg_data
    user = reg_data["user"]
    assert user["email"] == "learner@example.com"
    assert user["display_name"] == "Ada Lovelace"
    assert user["arm"] in ALL_ARMS
    assert user["consent_at"] is None

    # 2. Duplicate registration fails
    dup_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "learner@example.com",
            "password": "secretpassword123",
            "display_name": "Ada Lovelace",
        },
    )
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "USER_ALREADY_EXISTS"

    # 3. Login with wrong password fails
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": "learner@example.com", "password": "wrongpassword"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["error"]["code"] == "INVALID_CREDENTIALS"

    # 4. Login with correct password succeeds
    good_login = client.post(
        "/api/v1/auth/login",
        json={"email": "learner@example.com", "password": "secretpassword123"},
    )
    assert good_login.status_code == 200
    token = good_login.json()["token"]
    assert token

    # 5. Access /auth/me with bearer token
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "learner@example.com"


def test_consent_flow() -> None:
    client = TestClient(app)

    # Register
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "student@example.com",
            "password": "password123",
            "display_name": "Charles Babbage",
        },
    ).json()
    token = reg["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Guarded route requires consent -> 403 CONSENT_REQUIRED
    guarded_resp = client.get("/api/v1/test/guarded-learning-route", headers=headers)
    assert guarded_resp.status_code == 403
    assert guarded_resp.json()["error"]["code"] == "CONSENT_REQUIRED"

    # Give consent
    consent_resp = client.post("/api/v1/auth/consent", headers=headers)
    assert consent_resp.status_code == 200
    consent_at = consent_resp.json()["consent_at"]
    assert consent_at is not None

    # Guarded route now succeeds
    guarded_after = client.get("/api/v1/test/guarded-learning-route", headers=headers)
    assert guarded_after.status_code == 200
    assert guarded_after.json()["status"] == "authorized"


def test_balanced_arm_assignment() -> None:
    client = TestClient(app)
    arm_counts: dict[str, int] = {arm: 0 for arm in ALL_ARMS}

    # Register 30 users to check balanced distribution
    for i in range(30):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"user{i}@example.com",
                "password": "password123",
                "display_name": f"User {i}",
            },
        )
        assert resp.status_code == 201
        arm = resp.json()["user"]["arm"]
        arm_counts[arm] += 1

    # In balanced allocation of 30 items across 3 arms, each must get exactly 10
    for arm in ALL_ARMS:
        assert arm_counts[arm] == 10


def test_delete_me() -> None:
    client = TestClient(app)
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "delete-me@example.com",
            "password": "password123",
            "display_name": "Delete Me",
        },
    ).json()
    token = reg["token"]
    headers = {"Authorization": f"Bearer {token}"}

    del_resp = client.delete("/api/v1/me", headers=headers)
    assert del_resp.status_code == 204

    # Subsequent login fails
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "delete-me@example.com", "password": "password123"},
    )
    assert login_resp.status_code == 401
