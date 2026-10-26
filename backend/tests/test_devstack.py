"""The one-command local stack: `python -m app.devstack` runs on every `docker compose up`."""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import devstack
from app.db import models as m
from app.graph.demo_seed import DEMO_DOMAIN

CONTENT = Path(__file__).resolve().parents[2] / "content"


def _count(db: Session, where) -> int:
    return db.scalar(select(func.count()).select_from(m.User).where(where))


def test_prepare_is_safe_to_run_on_every_start(db: Session) -> None:
    first = devstack.prepare(db, CONTENT, admin_email="Admin@Example.com")
    assert any("demo learners: asha" in line for line in first)
    assert any(line.startswith("admin: admin@example.com (password") for line in first)
    assert db.scalar(select(func.count()).select_from(m.ConceptRow)) > 0

    learner = db.scalar(select(m.User).where(m.User.email == f"ben{DEMO_DOMAIN}"))
    learner.display_name = "Ben, changed in the app"
    db.flush()

    second = devstack.prepare(db, CONTENT, admin_email="admin@example.com")
    assert "demo learners: already there" in second
    assert "admin: admin@example.com already there" in second
    assert _count(db, m.User.email.like(f"%{DEMO_DOMAIN}")) == 3
    assert _count(db, m.User.is_admin.is_(True)) == 1
    # a restart keeps what people did in the app
    assert db.scalar(select(m.User.display_name).where(m.User.id == learner.id)) == (
        "Ben, changed in the app"
    )


def test_refuses_to_run_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    assert devstack.main([str(CONTENT)]) == 1
