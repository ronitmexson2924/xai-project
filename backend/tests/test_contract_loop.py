"""The closed loop from docs/ARCHITECTURE.md, run end-to-end through the fakes.

When a real service replaces a fake, run this same flow against it (see tasks M1 and R6).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contracts.explanation import ExplanationEventIn, ExplanationRequest, StyleParams
from app.contracts.fakes import (
    FakeExplainer,
    FakeFeedbackAnalyzer,
    FakeGraph,
    FakeLearnerModel,
    FakePlanner,
)
from app.contracts.learner import AttemptRecord


def _event(kind: str, at: datetime, **payload: object) -> ExplanationEventIn:
    return ExplanationEventIn(idempotency_key=uuid4(), type=kind, client_ts=at, payload=payload)


def test_closed_loop_through_fakes() -> None:
    graph = FakeGraph()
    learner, planner = FakeLearnerModel(), FakePlanner(graph)
    explainer, analyzer = FakeExplainer(graph), FakeFeedbackAnalyzer()
    user_id = uuid4()

    state = learner.get_state(user_id)
    rec = planner.next_step(state)
    style, source = planner.choose_style(state, rec.target_concept_id)
    explanation = explainer.explain(
        ExplanationRequest(
            user_id=user_id,
            recommendation_id=rec.id,
            concept_ids=[rec.target_concept_id],
            reasons=rec.reasons,
            style=style,
            style_source=source,
        )
    )
    analyzer.register(explanation)

    t0 = datetime.now(UTC)
    events = [
        _event("shown", t0),
        _event("hidden", t0 + timedelta(seconds=10)),
        _event("visible", t0 + timedelta(seconds=40)),
        _event("clarity_rated", t0 + timedelta(seconds=45), rating=2),
        _event("dismissed", t0 + timedelta(seconds=50)),
    ]
    assert analyzer.record_events(explanation.id, user_id, events) == (5, 0)
    assert analyzer.record_events(explanation.id, user_id, events) == (0, 5)

    item = graph.get_item(rec.item_id)
    attempt = AttemptRecord(
        id=uuid4(),
        user_id=user_id,
        item_id=item.id,
        concept_id=item.concept_id,
        response=item.answer,
        correct=True,
        latency_ms=4000,
        created_at=datetime.now(UTC),
    )
    mastery_delta = learner.apply_attempt(attempt)
    assert (
        mastery_delta.mastery_changes[item.concept_id][1]
        > mastery_delta.mastery_changes[item.concept_id][0]
    )

    summary = analyzer.summarize(explanation.id)
    assert summary.effective_dwell_ms == 20_000  # hidden time is excluded
    assert summary.clarity_rating == 2
    trait_delta = learner.apply_explanation_feedback(summary)
    assert "abstraction_preference" in trait_delta.trait_changes
    assert learner.apply_explanation_feedback(summary).trait_changes == {}  # idempotent


def test_variant_key_ignores_wrapper_fields() -> None:
    a = StyleParams(example_first=True, length="short", depth="why", tone="encouraging")
    b = StyleParams(example_first=True, length="short", depth="why", include_diagram=True)
    assert a.variant_key() == b.variant_key() == "ex1-short-why"
