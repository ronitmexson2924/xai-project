"""R7: edge cases (deleted users, bad input, sparse item banks) and the query budget."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.contracts.explanation import ExplanationFeedbackSummary, StyleParams
from app.contracts.learner import AttemptRecord
from app.db import models as m
from app.graph.content import ContentBundle
from app.graph.service import GraphSnapshot
from app.learner_model.service import LearnerModel
from app.planner.service import Planner
from tests.conftest import make_user


def attempt(user_id: uuid.UUID, item_id: str, concept_id: str, correct: bool = True):
    return AttemptRecord(
        id=uuid.uuid4(),
        user_id=user_id,
        item_id=item_id,
        concept_id=concept_id,
        response="3",
        correct=correct,
        latency_ms=5000,
        created_at=datetime.now(UTC),
    )


def test_deleted_users_are_treated_as_unknown(seeded: Session, graph: GraphSnapshot) -> None:
    model = LearnerModel(seeded, graph)
    user_id = make_user(seeded)
    seeded.get(m.User, user_id).deleted_at = datetime.now(UTC)
    seeded.flush()
    with pytest.raises(LookupError, match="deleted"):
        model.get_state(user_id)
    with pytest.raises(LookupError, match="deleted"):
        model.apply_attempt(attempt(user_id, "t-loops-mcq", "loops"))


def test_bad_attempts_are_rejected(seeded: Session, graph: GraphSnapshot) -> None:
    model = LearnerModel(seeded, graph)
    user_id = make_user(seeded)
    with pytest.raises(LookupError, match="unknown item"):
        model.apply_attempt(attempt(user_id, "no-such-item", "loops"))
    with pytest.raises(ValueError, match="does not match"):
        model.apply_attempt(attempt(user_id, "t-loops-mcq", "functions"))
    with pytest.raises(LookupError):
        model.apply_attempt(attempt(uuid.uuid4(), "t-loops-mcq", "loops"))


def test_feedback_with_unknown_concept_is_rejected(seeded: Session, graph: GraphSnapshot) -> None:
    model = LearnerModel(seeded, graph)
    user_id = make_user(seeded)
    summary = ExplanationFeedbackSummary(
        explanation_id=uuid.uuid4(),
        user_id=user_id,
        concept_ids=["not-a-concept"],
        style=StyleParams(example_first=True, length="short", depth="how"),
        style_source="generic",
        effective_dwell_ms=1000,
        clarity_rating=4,
    )
    with pytest.raises(ValueError, match="unknown concepts"):
        model.apply_explanation_feedback(summary)


def test_planner_only_uses_concepts_that_have_items(seeded: Session, graph: GraphSnapshot) -> None:
    """The shared fixture has practice items on `loops` only; 62 concepts have none."""
    model = LearnerModel(seeded, graph)
    planner = Planner(seeded, graph, model)
    user_id = make_user(seeded)
    for _ in range(3):
        rec = planner.next_step(model.get_state(user_id))
        assert rec.target_concept_id == "loops"
        model.apply_attempt(attempt(user_id, rec.item_id, "loops"))


def test_planner_needs_at_least_one_practice_item(seeded: Session, bundle: ContentBundle) -> None:
    empty = GraphSnapshot.from_bundle(bundle.model_copy(update={"items": []}))
    with pytest.raises(LookupError, match="no approved practice items"):
        Planner(seeded, empty, LearnerModel(seeded, empty))


def test_query_budget_per_learning_step(seeded: Session, graph: GraphSnapshot) -> None:
    """A full step (next + style + attempt) stays within a fixed number of SQL statements, so a
    regression such as an N+1 query over concepts fails here."""
    model = LearnerModel(seeded, graph)
    planner = Planner(seeded, graph, model)
    user_id = make_user(seeded)
    model.apply_attempt(attempt(user_id, "t-loops-mcq", "loops"))  # warm caches

    statements: list[str] = []
    engine = seeded.get_bind().engine

    def count(*args) -> None:
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", count)
    try:
        state = model.get_state(user_id)
        rec = planner.next_step(state)
        planner.choose_style(state, rec.target_concept_id)
        model.apply_attempt(attempt(user_id, rec.item_id, rec.target_concept_id))
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert len(statements) <= 18, "\n".join(statements)  # 16 measured in R7
