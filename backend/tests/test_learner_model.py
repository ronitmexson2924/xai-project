"""R2: LearnerModel.get_state / apply_attempt against Postgres."""

import time
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contracts.learner import AttemptRecord
from app.db import models as m
from app.graph.service import GraphSnapshot
from app.learner_model.service import LearnerModel
from tests.conftest import make_user


def attempt(user_id: uuid.UUID, item_id: str, concept_id: str, response: str, correct: bool):
    return AttemptRecord(
        id=uuid.uuid4(),
        user_id=user_id,
        item_id=item_id,
        concept_id=concept_id,
        response=response,
        correct=correct,
        latency_ms=5000,
        created_at=datetime.now(UTC),
    )


def test_new_learner_state(seeded: Session, graph: GraphSnapshot) -> None:
    user_id = make_user(seeded, arm="static_personalized")
    state = LearnerModel(seeded, graph).get_state(user_id)
    assert state.arm == "static_personalized"
    assert state.mastery == {} and state.total_attempts == 0
    assert all(t.mean == 0.5 for t in state.traits.traits.values())
    with pytest.raises(LookupError):
        LearnerModel(seeded, graph).get_state(uuid.uuid4())


def test_attempt_updates_mastery_from_prior(seeded: Session, graph: GraphSnapshot) -> None:
    model = LearnerModel(seeded, graph)
    user_id = make_user(seeded)
    prior = model.effective_mastery(model.get_state(user_id))["loops"]

    delta = model.apply_attempt(attempt(user_id, "t-loops-mcq", "loops", "3", True))

    before, after = delta.mastery_changes["loops"]
    assert before == pytest.approx(prior)
    assert after > before
    state = model.get_state(user_id)
    assert state.mastery["loops"].p_mastery == pytest.approx(after)
    assert state.total_attempts == 1
    assert seeded.scalar(select(func.count()).select_from(m.AttemptRow)) == 1


def test_replaying_an_attempt_changes_nothing(seeded: Session, graph: GraphSnapshot) -> None:
    model = LearnerModel(seeded, graph)
    user_id = make_user(seeded)
    a = attempt(user_id, "t-loops-mcq", "loops", "3", True)
    first = model.apply_attempt(a)
    second = model.apply_attempt(a)
    assert first == second
    assert model.get_state(user_id).mastery["loops"].n_attempts == 1
    assert seeded.scalar(select(func.count()).select_from(m.StateUpdateRow)) == 1


def test_misconception_flagged_then_cleared(seeded: Session, graph: GraphSnapshot) -> None:
    model = LearnerModel(seeded, graph)
    user_id = make_user(seeded)
    delta = model.apply_attempt(attempt(user_id, "t-loops-mcq", "loops", "4", False))
    assert "misconception flagged: loops-off-by-one" in delta.notes
    assert model.get_state(user_id).mastery["loops"].misconception_ids == ["loops-off-by-one"]

    model.apply_attempt(attempt(user_id, "t-loops-mcq", "loops", "3", True))
    assert model.get_state(user_id).mastery["loops"].misconception_ids == ["loops-off-by-one"]
    cleared = model.apply_attempt(attempt(user_id, "t-loops-short", "loops", "[1, 2, 3]", True))
    assert cleared.notes == ["misconceptions cleared: loops-off-by-one"]
    assert model.get_state(user_id).mastery["loops"].misconception_ids == []


def test_get_state_is_fast_for_a_full_graph(seeded: Session, graph: GraphSnapshot) -> None:
    user_id = make_user(seeded)
    seeded.add_all(
        m.LearnerConceptStateRow(user_id=user_id, concept_id=c, p_mastery=0.5, n_attempts=1)
        for c in graph.concept_ids
    )
    seeded.flush()
    model = LearnerModel(seeded, graph)
    model.get_state(user_id)  # warm up connection and statement cache
    start = time.perf_counter()
    state = model.get_state(user_id)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert len(state.mastery) == len(graph.concept_ids)
    assert elapsed_ms < 50, f"get_state took {elapsed_ms:.1f} ms"
