import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.db import models as m
from app.graph.content import ContentBundle, ItemSpec, load_content
from app.graph.seed import seed
from app.graph.service import GraphSnapshot

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://pcg:pcg@localhost:5432/pcg_test"
)


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """Migrate the test database from scratch once per run (exercising downgrade too)."""
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    """A session whose work (including commits) is rolled back after each test."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        yield session
        session.close()
        transaction.rollback()


# --- content + learner fixtures shared by the learner-model and planner tests ------------------

CONTENT_DIR = Path(__file__).parents[2] / "content"


def _test_items() -> list[ItemSpec]:
    return [
        ItemSpec(
            id="t-loops-mcq",
            concept_id="loops",
            kind="mcq",
            stem="How many times does `for i in range(3)` run?",
            options=["2", "3", "4"],
            answer="3",
            distractor_misconceptions={"4": "loops-off-by-one"},
            review_status="approved",
        ),
        ItemSpec(
            id="t-loops-short",
            concept_id="loops",
            kind="short",
            stem="What is list(range(1, 4))?",
            answer="[1, 2, 3]",
            review_status="approved",
        ),
        ItemSpec(
            id="t-rbc-check",
            concept_id="recursion-base-case",
            kind="mcq",
            stem="What does fact(0) return?",
            options=["0", "1", "It never returns"],
            answer="1",
            distractor_misconceptions={"It never returns": "recursion-no-base-case"},
            is_microcheck=True,
            review_status="approved",
        ),
    ]


@pytest.fixture(scope="session")
def bundle() -> ContentBundle:
    content = load_content(CONTENT_DIR)
    content.items = [*content.items, *_test_items()]
    return content


@pytest.fixture(scope="session")
def graph(bundle: ContentBundle) -> GraphSnapshot:
    return GraphSnapshot.from_bundle(bundle)


@pytest.fixture
def seeded(db: Session, bundle: ContentBundle) -> Session:
    seed(db, bundle)
    return db


def make_user(db: Session, arm: str = "closed_loop") -> uuid.UUID:
    user_id = uuid.uuid4()
    db.add(m.User(id=user_id, email=f"{user_id}@test", password_hash="x", display_name="T"))
    db.flush()
    db.add(m.ExperimentAssignment(user_id=user_id, arm=arm))
    db.flush()
    return user_id


# --- HTTP API fixtures (Mit's routes over the real services) -----------------------------------


class ApiClient:
    """A TestClient plus helpers that walk a learner through the real API."""

    def __init__(self, client, session: Session) -> None:  # noqa: ANN001
        self.client = client
        self.session = session
        self._n = 0

    def __getattr__(self, name: str):  # noqa: ANN204 (get/post/delete pass through)
        return getattr(self.client, name)

    def register(self, email: str | None = None, password: str = "correct horse 1") -> dict:
        self._n += 1
        email = email or f"learner{self._n}-{uuid.uuid4().hex[:6]}@example.com"
        r = self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "display_name": f"Learner {self._n}"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        return {
            "token": body["token"],
            "user": body["user"],
            "email": email,
            "password": password,
            "h": {"Authorization": f"Bearer {body['token']}"},
        }

    def learner(self, questionnaire: bool = True) -> dict:
        """Registered, consented and (by default) through the questionnaire."""
        who = self.register()
        assert self.client.post("/api/v1/auth/consent", headers=who["h"]).status_code == 200
        if questionnaire:
            items = self.client.get("/api/v1/onboarding/questionnaire", headers=who["h"]).json()
            answers = {i["id"]: 3 for i in items}
            r = self.client.post(
                "/api/v1/onboarding/questionnaire", json={"answers": answers}, headers=who["h"]
            )
            assert r.status_code == 200, r.text
        return who

    def admin(self) -> dict:
        who = self.learner(questionnaire=False)
        self.session.get(m.User, uuid.UUID(who["user"]["id"])).is_admin = True
        self.session.flush()
        return who

    def next(self, who: dict) -> dict:
        r = self.client.post("/api/v1/session/next", headers=who["h"])
        assert r.status_code == 200, r.text
        return r.json()

    def answer(self, who: dict, step: dict, correct: bool = True) -> dict:
        item = step["item"]
        response = self.answer_text(item, correct)
        r = self.client.post(
            "/api/v1/attempts",
            json={
                "item_id": item["id"],
                "response": response,
                "latency_ms": 9000,
                "recommendation_id": step["recommendation"]["id"],
            },
            headers=who["h"],
        )
        assert r.status_code == 200, r.text
        return r.json()

    @staticmethod
    def answer_text(item: dict, correct: bool) -> str:
        # simulation items: option "a" is right (research/simulator/world.py)
        return "a" if correct else "b"


@pytest.fixture
def api(db: Session) -> Iterator[ApiClient]:
    from fastapi.testclient import TestClient

    from app.api import deps
    from app.api.middleware import reset_rate_limiter
    from app.auth.db import get_session
    from app.config import settings
    from app.main import app
    from simulator.world import simulation_bundle

    bundle = simulation_bundle()
    seed(db, bundle)
    db.commit()
    deps.set_graph(GraphSnapshot.from_bundle(bundle))
    app.dependency_overrides[get_session] = lambda: db
    old = settings.rate_limit_enabled, settings.export_salt, settings.jwt_secret
    settings.rate_limit_enabled = False
    settings.jwt_secret = "test-secret-" + "x" * 40
    reset_rate_limiter()
    try:
        yield ApiClient(TestClient(app), db)
    finally:
        settings.rate_limit_enabled, settings.export_salt, settings.jwt_secret = old
        app.dependency_overrides.clear()
        deps.set_graph(None)
        reset_rate_limiter()
