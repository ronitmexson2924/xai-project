"""R5 (DB): explanation feedback and attempts update traits, suspicion and affect per arm."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.contracts.explanation import ExplanationFeedbackSummary, StyleParams
from app.contracts.learner import AttemptRecord
from app.db import models as m
from app.graph.service import GraphSnapshot
from app.learner_model.bandit import BanditPosterior
from app.learner_model.service import LearnerModel, StaleTraitsError
from app.planner.service import Planner
from tests.conftest import make_user

T0 = datetime(2026, 10, 25, 10, 0, tzinfo=UTC)
STYLE = StyleParams(example_first=False, length="long", depth="why")


def make_explanation(db: Session, user_id: uuid.UUID, concept_id: str) -> uuid.UUID:
    rec_id, exp_id = uuid.uuid4(), uuid.uuid4()
    db.add(
        m.RecommendationRow(
            id=rec_id,
            user_id=user_id,
            kind="remediate",
            target_concept_id=concept_id,
            reasons=[],
            policy_version="test",
        )
    )
    db.flush()
    db.add(
        m.ExplanationRow(
            id=exp_id,
            recommendation_id=rec_id,
            user_id=user_id,
            concept_ids=[concept_id],
            style=STYLE.model_dump(),
            style_source="thompson",
            body_markdown="...",
            source="template",
            prompt_version="test",
        )
    )
    db.flush()
    return exp_id


def attempt(user_id, item_id, concept_id, response, correct, at, **extra) -> AttemptRecord:
    return AttemptRecord(
        id=uuid.uuid4(),
        user_id=user_id,
        item_id=item_id,
        concept_id=concept_id,
        response=response,
        correct=correct,
        latency_ms=extra.pop("latency_ms", 8000),
        created_at=at,
        **extra,
    )


def feedback(user_id, exp_id, **fields) -> ExplanationFeedbackSummary:
    return ExplanationFeedbackSummary(
        explanation_id=exp_id,
        user_id=user_id,
        concept_ids=["recursion-base-case"],
        style=STYLE,
        style_source="thompson",
        effective_dwell_ms=30_000,
        **fields,
    )


def test_closed_loop_feedback_updates_style_traits(seeded: Session, graph: GraphSnapshot) -> None:
    model = LearnerModel(seeded, graph)
    user_id = make_user(seeded, arm="closed_loop")
    exp_id = make_explanation(seeded, user_id, "recursion-base-case")
    model.apply_attempt(
        attempt(user_id, "t-rbc-check", "recursion-base-case", "1", True, T0, explanation_id=exp_id)
    )

    delta = model.apply_explanation_feedback(
        feedback(user_id, exp_id, followup_correct=True, clarity_rating=5)
    )

    # rule-first, long, why worked well -> all three style traits move up
    for trait in ("abstraction_preference", "load_tolerance", "depth_preference"):
        before, after = delta.trait_changes[trait]
        assert after > before
    row = seeded.get(m.LearnerTraitsRow, user_id)
    assert row.version == 1 and BanditPosterior.from_json(row.bandit).n == 1
    assert any(note.startswith("style outcome y = +") for note in delta.notes)

    assert model.apply_explanation_feedback(feedback(user_id, exp_id, clarity_rating=1)) == delta
    assert seeded.get(m.LearnerTraitsRow, user_id).version == 1  # replay changed nothing


def test_confusing_explanation_raises_suspicion_in_every_arm(
    seeded: Session, graph: GraphSnapshot
) -> None:
    model = LearnerModel(seeded, graph)
    for arm in ("generic", "static_personalized"):
        user_id = make_user(seeded, arm=arm)
        exp_id = make_explanation(seeded, user_id, "recursion-base-case")
        delta = model.apply_explanation_feedback(
            feedback(user_id, exp_id, followup_correct=False, clarity_rating=1)
        )
        assert delta.trait_changes == {}  # no trait learning outside the closed loop
        state = model.get_state(user_id)
        assert state.mastery["recursion-base-case"].misconception_suspicion == 0.25


def test_feedback_without_signal_only_touches_engagement(
    seeded: Session, graph: GraphSnapshot
) -> None:
    model = LearnerModel(seeded, graph)
    user_id = make_user(seeded)
    exp_id = make_explanation(seeded, user_id, "recursion-base-case")
    delta = model.apply_explanation_feedback(feedback(user_id, exp_id, dismissed_quickly=True))
    assert delta.trait_changes == {}
    assert model.get_state(user_id).affect.engagement == pytest.approx(0.4)


def test_behavioural_traits_update_only_in_closed_loop(
    seeded: Session, graph: GraphSnapshot
) -> None:
    model = LearnerModel(seeded, graph)
    for arm, should_change in (("closed_loop", True), ("generic", False)):
        user_id = make_user(seeded, arm=arm)
        model.apply_attempt(attempt(user_id, "t-loops-mcq", "loops", "2", False, T0))
        delta = model.apply_attempt(
            attempt(
                user_id, "t-loops-mcq", "loops", "3", True, T0 + timedelta(minutes=1), confidence=5
            )
        )
        assert ("persistence" in delta.trait_changes) is should_change
        assert ("self_efficacy" in delta.trait_changes) is should_change
        if should_change:
            assert delta.trait_changes["persistence"][1] > 0.5


def test_affect_tracks_frustration_and_fatigue(seeded: Session, graph: GraphSnapshot) -> None:
    model = LearnerModel(seeded, graph)
    user_id = make_user(seeded)
    for k in range(3):  # three fast wrong answers, 10 minutes apart
        model.apply_attempt(
            attempt(
                user_id,
                "t-loops-mcq",
                "loops",
                "4",
                False,
                T0 + timedelta(minutes=10 * k),
                latency_ms=1500,
            )
        )
    affect = model.get_state(user_id).affect
    assert affect.frustration > 0.6
    assert affect.fatigue == pytest.approx(20 / 40)

    model.apply_attempt(  # after a 2-hour break a new session starts
        attempt(user_id, "t-loops-mcq", "loops", "3", True, T0 + timedelta(hours=3))
    )
    assert model.get_state(user_id).affect.fatigue == 0.0


def test_stale_trait_write_is_detected_and_retried(seeded: Session, graph: GraphSnapshot) -> None:
    model = LearnerModel(seeded, graph)
    user_id = make_user(seeded)
    model.init_from_questionnaire(user_id, {})  # creates traits at version 1
    traits, posterior = model._load_traits(user_id)
    seeded.get(m.LearnerTraitsRow, user_id).version = 5  # someone else wrote meanwhile
    seeded.flush()
    with pytest.raises(StaleTraitsError):
        model._save_traits(user_id, traits, posterior, expected=traits.version)

    class FlakyOnce(LearnerModel):
        failed = False

        def _save_traits(self, *args, **kwargs) -> None:
            if not FlakyOnce.failed:
                FlakyOnce.failed = True
                raise StaleTraitsError(user_id)
            super()._save_traits(*args, **kwargs)

    exp_id = make_explanation(seeded, user_id, "recursion-base-case")
    delta = FlakyOnce(seeded, graph).apply_explanation_feedback(
        feedback(user_id, exp_id, clarity_rating=5)
    )
    assert FlakyOnce.failed and delta.trait_changes
    assert seeded.get(m.LearnerTraitsRow, user_id).version == 6


def test_planner_choose_style_per_arm(seeded: Session, graph: GraphSnapshot) -> None:
    model = LearnerModel(seeded, graph)
    planner = Planner(seeded, graph, model, seed=3)
    sources = {}
    for arm in ("generic", "static_personalized", "closed_loop"):
        user_id = make_user(seeded, arm=arm)
        style, sources[arm] = planner.choose_style(model.get_state(user_id), "recursion-base-case")
        assert isinstance(style, StyleParams)
    assert sources["generic"] == "generic"
    assert sources["static_personalized"] == "trait_mapped"
    assert sources["closed_loop"] in ("thompson", "exploration")
