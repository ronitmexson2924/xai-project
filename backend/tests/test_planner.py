"""R4: one scenario per planner rule (docs/MODEL_SPEC.md §5), determinism and item choice."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.contracts.planning import Recommendation
from app.contracts.reasons import ReasonCode
from app.db import models as m
from app.graph.content import ContentBundle, ItemSpec
from app.graph.seed import seed
from app.graph.service import GraphSnapshot
from app.learner_model.service import LearnerModel
from app.planner.service import Planner
from tests.conftest import make_user

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def planner_bundle(bundle: ContentBundle) -> ContentBundle:
    """The real graph with two generated practice items on every concept."""
    items = [
        ItemSpec(
            id=f"gen-{c.id}-{k}",
            concept_id=c.id,
            kind="mcq",
            stem=f"Question {k} about {c.name}",
            options=["a", "b", "c", "d"],
            answer="a",
            difficulty=1 + 2 * k,
            review_status="approved",
        )
        for c in bundle.concepts
        for k in range(2)
    ]
    return bundle.model_copy(update={"items": items})


@pytest.fixture
def setup(db: Session, planner_bundle: ContentBundle):
    seed(db, planner_bundle)
    graph = GraphSnapshot.from_bundle(planner_bundle)
    model = LearnerModel(db, graph)
    planner = Planner(db, graph, model, seed=1, now=lambda: NOW)
    return db, graph, model, planner


def set_concepts(db: Session, user_id: uuid.UUID, **concepts: dict) -> None:
    for concept_id, fields in concepts.items():
        db.add(
            m.LearnerConceptStateRow(
                user_id=user_id,
                concept_id=concept_id.replace("_", "-"),
                p_mastery=fields.get("p", 0.5),
                n_attempts=fields.get("n", 1),
                streak=fields.get("streak", 0),
                misconception_ids=fields.get("misconceptions", []),
                misconception_suspicion=fields.get("suspicion", 0.0),
                updated_at=fields.get("updated_at", NOW),
            )
        )
    db.flush()


def step(model: LearnerModel, planner: Planner, user_id: uuid.UUID) -> Recommendation:
    return planner.next_step(model.get_state(user_id))


def test_new_learner_gets_diagnostic_items(setup) -> None:
    db, graph, model, planner = setup
    user_id = make_user(db)
    rec = step(model, planner, user_id)
    assert rec.kind == "diagnostic_item"
    assert rec.reasons[0].code == ReasonCode.DIAGNOSTIC
    assert rec.target_concept_id == "variables-and-types"  # the only depth-0 concept
    assert db.get(m.RecommendationRow, rec.id) is not None

    set_concepts(db, user_id, variables_and_types={"n": 1})
    second = step(model, planner, user_id)
    assert second.kind == "diagnostic_item" and second.target_concept_id != "variables-and-types"
    assert graph.depth[second.target_concept_id] >= 3


def test_planner_is_deterministic_for_same_state_and_seed(setup) -> None:
    db, graph, model, planner = setup
    user_id = make_user(db)
    set_concepts(db, user_id, variables_and_types={"n": 3})
    again = Planner(db, graph, model, seed=1, now=lambda: NOW)
    a, b = step(model, planner, user_id), step(model, again, user_id)
    assert (a.target_concept_id, a.item_id, a.reasons) == (
        b.target_concept_id,
        b.item_id,
        b.reasons,
    )


def test_detected_misconception_is_remediated_first(setup) -> None:
    db, graph, model, planner = setup
    user_id = make_user(db)
    set_concepts(db, user_id, loops={"n": 8, "p": 0.7, "misconceptions": ["loops-off-by-one"]})
    rec = step(model, planner, user_id)
    assert (rec.kind, rec.target_concept_id) == ("remediate", "loops")
    assert rec.reasons[0].code == ReasonCode.MISCONCEPTION_DETECTED
    assert rec.reasons[0].detail == graph.misconception("loops-off-by-one").description


def test_suspected_misconception_is_remediated(setup) -> None:
    db, _, model, planner = setup
    user_id = make_user(db)
    set_concepts(db, user_id, loops={"n": 8, "suspicion": 0.6})
    rec = step(model, planner, user_id)
    assert rec.target_concept_id == "loops"
    assert rec.reasons[0].code == ReasonCode.MISCONCEPTION_SUSPECTED


def test_struggle_with_weak_prerequisite_remediates_the_prerequisite(setup) -> None:
    db, _, model, planner = setup
    user_id = make_user(db)
    set_concepts(
        db,
        user_id,
        recursive_case={"n": 4, "p": 0.3, "streak": -2},
        recursion_base_case={"n": 4, "p": 0.3},
    )
    rec = step(model, planner, user_id)
    assert (rec.kind, rec.target_concept_id) == ("remediate", "recursion-base-case")
    assert rec.reasons[0].code == ReasonCode.PREREQ_GAP
    assert "Recursion: recursive case" in rec.reasons[0].detail


def test_frontier_continues_weakest_concept_in_progress(setup) -> None:
    db, _, model, planner = setup
    user_id = make_user(db)
    set_concepts(
        db,
        user_id,
        variables_and_types={"n": 4, "p": 0.97},
        conditionals={"n": 4, "p": 0.9},
        functions={"n": 1, "p": 0.5},
    )
    rec = step(model, planner, user_id)
    assert (rec.kind, rec.target_concept_id) == ("practice_item", "functions")
    assert rec.reasons[0].code == ReasonCode.READY_FOR_NEXT


def test_frontier_advances_when_nothing_is_in_progress(setup) -> None:
    db, graph, model, planner = setup
    user_id = make_user(db)
    set_concepts(db, user_id, variables_and_types={"n": 9, "p": 0.97})
    rec = step(model, planner, user_id)
    assert rec.kind == "advance"
    assert graph.prerequisites(rec.target_concept_id) == ["variables-and-types"]


def test_review_of_stale_mastered_concept_on_review_turn(setup) -> None:
    db, _, model, planner = setup
    user_id = make_user(db)
    stale = NOW - timedelta(days=3)
    set_concepts(db, user_id, variables_and_types={"n": 11, "p": 0.97, "updated_at": stale})
    rec = step(model, planner, user_id)  # 11 attempts: 11 % 6 == 5 -> review turn
    assert (rec.kind, rec.target_concept_id) == ("review", "variables-and-types")
    assert rec.reasons[0].code == ReasonCode.REVIEW_DUE

    other = make_user(db)
    set_concepts(db, other, variables_and_types={"n": 10, "p": 0.97, "updated_at": stale})
    assert step(model, planner, other).kind == "advance"  # not a review turn


def test_recently_seen_item_is_not_repeated(setup) -> None:
    db, _, model, planner = setup
    user_id = make_user(db)
    set_concepts(db, user_id, loops={"n": 8, "misconceptions": ["loops-off-by-one"]})
    first = step(model, planner, user_id)
    db.add(
        m.AttemptRow(
            user_id=user_id, item_id=first.item_id, response="a", correct=True, latency_ms=1
        )
    )
    db.flush()
    second = step(model, planner, user_id)
    assert second.target_concept_id == first.target_concept_id
    assert second.item_id != first.item_id
