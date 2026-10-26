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
    """The real concept graph with the fixture items only, so tests don't depend on the item bank
    (content/items/, Mit). test_content.py validates the real bank."""
    content = load_content(CONTENT_DIR)
    content.items = _test_items()
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


# --- API fixtures: the real app on the per-test database session ----------------------------------


def _api_items() -> list[ItemSpec]:
    """Fixture items plus a second practice concept and parallel pre/post tests."""
    return [
        *_test_items(),
        ItemSpec(
            id="t-vars-mcq",
            concept_id="variables-and-types",
            kind="mcq",
            stem="x = 1; y = x; x = 2. What is y?",
            options=["1", "2", "None"],
            answer="1",
            distractor_misconceptions={"2": "vars-assignment-links-names"},
            review_status="approved",
        ),
        ItemSpec(
            id="t-draft",
            concept_id="loops",
            kind="mcq",
            stem="An unreviewed question",
            options=["a", "b"],
            answer="a",
            review_status="draft",
        ),
        *(
            ItemSpec(
                id=f"{phase}-{n}",
                concept_id="loops",
                kind="mcq",
                stem=f"{phase} question {n}",
                options=["right", "wrong"],
                answer="right",
                review_status="approved",
            )
            for phase in ("pretest", "posttest")
            for n in (1, 2)
        ),
    ]


@pytest.fixture
def client(db: Session, bundle: ContentBundle, monkeypatch: pytest.MonkeyPatch):
    from fastapi.testclient import TestClient

    from app.api.deps import reload_graph
    from app.api.middleware import reset_rate_limiter
    from app.auth.limits import login_throttle
    from app.config import settings
    from app.db.session import get_db
    from app.main import app

    seed(db, bundle.model_copy(update={"items": _api_items()}))
    db.commit()
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-" + "x" * 32)
    monkeypatch.setattr(settings, "analysis_salt", "test-salt-0123456789")
    reload_graph()
    reset_rate_limiter()
    login_throttle.reset()

    def override_db() -> Iterator[Session]:
        try:
            yield db
        finally:
            db.rollback()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    reload_graph()
