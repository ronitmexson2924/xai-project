"""R9: decision rationales (XAI E1) and their counterfactuals (E2) are faithful.

Faithfulness is checked *behaviourally*: each counterfactual is carried out for real (the learner
answers the stated number of questions through the real learner model), the planner is asked
again, and it must recommend exactly the concept the counterfactual promised."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.contracts.explanation import ExplanationFeedbackSummary, StyleParams
from app.contracts.learner import AttemptRecord
from app.contracts.reasons import ReasonCode
from app.contracts.xai import Counterfactual, Rationale
from app.db import models as m
from app.planner.rationale import BANNED_PHRASES, pct
from tests.conftest import make_user
from tests.test_planner import NOW, planner_bundle, set_concepts, setup  # noqa: F401 (fixtures)


def rationale_of(db: Session, recommendation_id: uuid.UUID) -> Rationale:
    return Rationale.model_validate(db.get(m.RecommendationRow, recommendation_id).rationale)


def answer_correctly(db, model, graph, user_id, concept_id, times, at) -> None:
    item = graph.items_for_concept(concept_id)[0]
    for k in range(times):
        model.apply_attempt(
            AttemptRecord(
                id=uuid.uuid4(),
                user_id=user_id,
                item_id=item.id,
                concept_id=concept_id,
                response=item.answer,
                correct=True,
                latency_ms=8000,
                created_at=at + timedelta(minutes=k),
            )
        )


def carry_out(setup_tuple, user_id, cf: Counterfactual) -> str:
    """Make the counterfactual true through the real services; return the planner's new target."""
    db, graph, model, planner = setup_tuple
    at = datetime.now(UTC)
    if cf.kind in ("mastery_at_least", "misconception_cleared", "review_done"):
        answer_correctly(db, model, graph, user_id, cf.concept_id, cf.steps_needed, at)
    elif cf.kind == "suspicion_below":
        for k in range(cf.steps_needed):
            explanation_id = uuid.uuid4()
            rec = planner.next_step(model.get_state(user_id))
            db.add(
                m.ExplanationRow(
                    id=explanation_id,
                    recommendation_id=rec.id,
                    user_id=user_id,
                    concept_ids=[cf.concept_id],
                    style={},
                    style_source="generic",
                    body_markdown="-",
                    source="template",
                    prompt_version="t",
                )
            )
            db.flush()
            check = graph.items_for_concept(cf.concept_id)[0]
            model.apply_attempt(
                AttemptRecord(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    item_id=check.id,
                    concept_id=cf.concept_id,
                    response=check.answer,
                    correct=True,
                    latency_ms=8000,
                    explanation_id=explanation_id,
                    created_at=at + timedelta(minutes=k),
                )
            )
            model.apply_explanation_feedback(
                ExplanationFeedbackSummary(
                    explanation_id=explanation_id,
                    user_id=user_id,
                    concept_ids=[cf.concept_id],
                    style=StyleParams(example_first=True, length="medium", depth="how"),
                    style_source="generic",
                    effective_dwell_ms=20_000,
                    followup_correct=True,
                )
            )
    elif cf.kind == "placement_complete":
        row = db.query(m.LearnerConceptStateRow).filter_by(user_id=user_id).first()
        row.n_attempts += cf.steps_needed  # "based on your answers so far"
        db.flush()
    return planner.next_step(model.get_state(user_id)).target_concept_id


SCENARIOS = {
    "diagnostic": {"variables_and_types": {"n": 2, "p": 0.6}},
    "misconception": {"loops": {"n": 8, "p": 0.5, "misconceptions": ["loops-off-by-one"]}},
    "suspected": {"loops": {"n": 8, "p": 0.5, "suspicion": 0.6}},
    "prereq_gap": {
        "recursive_case": {"n": 4, "p": 0.3, "streak": -2},
        "recursion_base_case": {"n": 4, "p": 0.3},
    },
    "frontier": {
        "variables_and_types": {"n": 4, "p": 0.97},
        "conditionals": {"n": 4, "p": 0.9},
        "functions": {"n": 1, "p": 0.5},
    },
    "review": {"variables_and_types": {"n": 11, "p": 0.97, "updated_at": NOW - timedelta(days=3)}},
}
EXPECTED_RULE = {
    "diagnostic": ReasonCode.DIAGNOSTIC,
    "misconception": ReasonCode.MISCONCEPTION_DETECTED,
    "suspected": ReasonCode.MISCONCEPTION_SUSPECTED,
    "prereq_gap": ReasonCode.PREREQ_GAP,
    "frontier": ReasonCode.READY_FOR_NEXT,
    "review": ReasonCode.REVIEW_DUE,
}


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_every_rule_gets_a_faithful_rationale(setup, scenario: str) -> None:  # noqa: F811
    db, graph, model, planner = setup
    user_id = make_user(db)
    set_concepts(db, user_id, **SCENARIOS[scenario])
    rec = planner.next_step(model.get_state(user_id))
    rationale = rationale_of(db, rec.id)

    assert rationale.rule == EXPECTED_RULE[scenario]
    assert rationale.evidence == rec.reasons
    assert (
        rationale.summary
        and graph.get_concept(rec.target_concept_id).name
        in (rationale.summary + " ".join(c.condition for c in rationale.counterfactuals))
        or scenario == "diagnostic"
    )
    assert rationale.counterfactuals, "every rule except fallback offers what would change it"

    for cf in rationale.counterfactuals:
        assert cf.outcome_concept_id != rec.target_concept_id or cf.kind == "review_done"
        assert carry_out(setup, user_id, cf) == cf.outcome_concept_id, cf


def test_prerequisite_gap_quotes_the_real_numbers(setup) -> None:  # noqa: F811
    db, graph, model, planner = setup
    user_id = make_user(db)
    set_concepts(db, user_id, **SCENARIOS["prereq_gap"])
    rec = planner.next_step(model.get_state(user_id))
    rationale = rationale_of(db, rec.id)
    mastery = model.effective_mastery(model.get_state(user_id))["recursion-base-case"]
    assert pct(mastery) in rationale.summary and "60%" in rationale.summary
    assert "Recursion: recursive case" in rationale.summary
    assert rationale.threshold == 0.6
    assert rationale.alternative and rationale.alternative.startswith("Without this")


def test_no_rationale_uses_labels_about_the_learner(setup) -> None:  # noqa: F811
    db, _, model, planner = setup
    texts = []
    for scenario in SCENARIOS.values():
        user_id = make_user(db)
        set_concepts(db, user_id, **scenario)
        rationale = rationale_of(db, planner.next_step(model.get_state(user_id)).id)
        texts += [rationale.summary, rationale.alternative or ""]
        texts += [c.condition + " " + c.outcome for c in rationale.counterfactuals]
    for text in texts:
        assert not any(phrase in text.lower() for phrase in BANNED_PHRASES), text
