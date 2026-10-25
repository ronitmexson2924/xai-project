"""Drive the API like a learner's browser would (used by the API and security tests)."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db import models as m

API = "/api/v1"
PASSWORD = "Correct-horse-9"


@dataclass
class Learner:
    client: TestClient
    email: str
    token: str
    id: uuid.UUID
    arm: str
    password: str = PASSWORD
    last: dict = field(default_factory=dict)

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, path: str, **kw):
        return self.client.get(API + path, headers=self.headers, **kw)

    def post(self, path: str, json=None, **kw):
        return self.client.post(API + path, headers=self.headers, json=json, **kw)

    def delete(self, path: str, **kw):
        return self.client.delete(API + path, headers=self.headers, **kw)

    def consent(self) -> "Learner":
        assert self.post("/auth/consent").status_code == 200
        return self

    def questionnaire(self, value: int = 4) -> dict:
        items = self.get("/onboarding/questionnaire").json()
        r = self.post("/onboarding/questionnaire", {"answers": {i["id"]: value for i in items}})
        assert r.status_code == 200, r.text
        return r.json()

    def next(self) -> dict:
        r = self.post("/session/next")
        assert r.status_code == 200, r.text
        self.last = r.json()
        return self.last

    def answer(self, response: str | None = None, step: dict | None = None, **extra):
        step = step or self.last
        item = step["item"]
        body = {
            "item_id": item["id"],
            "response": response
            if response is not None
            else (item["options"][0] if item["options"] else "a guess"),
            "latency_ms": 4000,
            "recommendation_id": step["recommendation"]["id"],
            "explanation_id": step["explanation"]["id"],
        } | extra
        return self.post("/attempts", body)

    def events(self, explanation_id: str, *events: tuple[str, int, dict]):
        """events: (type, seconds after now, payload)."""
        now = datetime.now(UTC)
        return self.post(
            f"/explanations/{explanation_id}/events",
            {
                "events": [
                    {
                        "idempotency_key": str(uuid.uuid4()),
                        "type": kind,
                        "client_ts": (now + timedelta(seconds=s)).isoformat(),
                        "payload": payload,
                    }
                    for kind, s, payload in events
                ]
            },
        )


def register(client: TestClient, email: str | None = None, password: str = PASSWORD) -> Learner:
    email = email or f"learner-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "display_name": "Test Learner"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return Learner(
        client,
        email,
        body["token"],
        uuid.UUID(body["user"]["id"]),
        body["user"]["arm"],
        password,
    )


def learner(client: TestClient, db: Session, arm: str | None = None) -> Learner:
    """A consented learner, optionally moved to a given arm."""
    who = register(client).consent()
    if arm is not None:
        db.execute(
            update(m.ExperimentAssignment)
            .where(m.ExperimentAssignment.user_id == who.id)
            .values(arm=arm)
        )
        db.commit()
        who.arm = arm
    return who


def admin(client: TestClient, db: Session) -> Learner:
    who = register(client)
    db.execute(update(m.User).where(m.User.id == who.id).values(is_admin=True))
    db.commit()
    return who
