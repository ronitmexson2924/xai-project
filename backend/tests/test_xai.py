"""R10: style rationale (E3), open-learner-model beliefs (E4), change notices (E5) and the
Explainability service, checked on the demo learners."""

import uuid
from datetime import UTC, datetime

import numpy as np
import pytest
from sqlalchemy.orm import Session

from app.contracts.explanation import StyleParams
from app.contracts.learner import (
    TRAIT_NAMES,
    AffectiveState,
    AttemptRecord,
    StateDelta,
)
from app.contracts.reasons import ReasonCode
from app.graph.demo_seed import START, build
from app.graph.service import GraphSnapshot
from app.learner_model.bandit import BanditPosterior, best_style
from app.learner_model.service import LearnerModel
from app.learner_model.traits import neutral_traits
from app.planner.rationale import BANNED_PHRASES
from app.planner.service import Planner
from app.planner.style import candidates, explain_style, p_best
from app.planner.xai import Explainability


@pytest.fixture
def demo(seeded: Session):
    users = build(seeded)
    graph = GraphSnapshot.from_db(seeded, include_drafts=True)
    model = LearnerModel(seeded, graph)
    planner = Planner(seeded, graph, model, seed=1, now=lambda: START)
    return seeded, graph, model, planner, Explainability(model), users


def test_why_returns_the_stored_rationale_and_style(demo) -> None:
    db, graph, model, planner, xai, users = demo
    state = model.get_state(users["ben"])
    rec = planner.next_step(state)
    assert xai.why(rec.id).style is None  # no style chosen yet
    planner.choose_style(state, rec.target_concept_id)
    why = xai.why(rec.id)

    flagged = state.mastery["recursion-base-case"].misconception_ids[0]
    assert why.rationale.rule == ReasonCode.MISCONCEPTION_DETECTED
    assert graph.misconception(flagged).description in why.rationale.summary
    assert [c.kind for c in why.rationale.counterfactuals] == ["misconception_cleared"]
    assert why.style.source == "trait_mapped"  # Ben is in the static arm
    assert why.style.summary.startswith("Based on your questionnaire answers")
    with pytest.raises(LookupError):
        xai.why(uuid.uuid4())


def test_closed_loop_style_rationale_quotes_the_evidence(demo) -> None:
    _, _, model, planner, xai, users = demo
    state = model.get_state(users["chen"])
    rec = planner.next_step(state)
    planner.choose_style(state, rec.target_concept_id)
    style = xai.why(rec.id).style
    assert style.source in ("thompson", "exploration") and style.p_best is not None
    if style.source == "thompson":
        assert "based on 24 explanations" in style.summary
    else:
        assert "trying a different style" in style.summary


def test_p_best_matches_an_independent_estimate() -> None:
    posterior = BanditPosterior.from_trait_priors(neutral_traits().traits)
    rng = np.random.default_rng(0)
    for _ in range(12):  # some evidence for rule-first, long, why
        posterior = posterior.update((False, "long", "why"), 0.4 + rng.normal(0, 0.3))
    choice = best_style(posterior.mean)
    estimate = p_best(posterior, choice, candidates(AffectiveState()), np.random.default_rng(1))
    draws = np.random.default_rng(2).multivariate_normal(posterior.mean, posterior.covariance, 4000)
    empirical = np.mean([best_style(theta) == choice for theta in draws])
    assert abs(estimate - empirical) < 0.05


def test_fatigue_is_explained() -> None:
    posterior = BanditPosterior.from_trait_priors(neutral_traits().traits)
    style = StyleParams(example_first=True, length="short", depth="how")
    tired = AffectiveState(fatigue=0.9)
    rationale = explain_style(style, "thompson", posterior, tired, np.random.default_rng(0))
    assert "kept short because you've been studying for a while" in rationale.summary


def test_trait_beliefs_reflect_evidence_and_confidence(demo) -> None:
    _, _, _, _, xai, users = demo
    chen = xai.explain_belief(users["chen"], "abstraction_preference")
    assert "general rule" in chen.summary and chen.confidence in ("moderate", "confident")
    assert len(chen.top_evidence) == 3
    assert all("feedback on an explanation" in e for e in chen.top_evidence)

    asha = xai.explain_belief(users["asha"], "abstraction_preference")
    assert "start with an example" in asha.summary and asha.confidence == "tentative"
    assert "only from your questionnaire" in asha.summary

    persistence = xai.explain_belief(users["asha"], "persistence")
    assert "never used to judge you" in persistence.summary


def test_concept_beliefs_point_at_the_answers(demo) -> None:
    _, _, _, _, xai, users = demo
    rbc = xai.explain_belief(users["ben"], "recursion-base-case")
    assert "Open issue" in rbc.summary and rbc.confidence == "tentative"
    assert rbc.top_evidence and "wrong answer lowered" in rbc.top_evidence[0]
    untouched = xai.explain_belief(users["ben"], "dijkstra")
    assert untouched.summary.startswith("You haven't answered questions")
    with pytest.raises(LookupError):
        xai.explain_belief(users["ben"], "not-a-thing")


def test_change_notices(demo) -> None:
    _, graph, model, _, xai, users = demo
    item = graph.items_for_concept("loops")[0]
    wrong_with_mistake = next(o for o in item.options if o in item.distractor_misconceptions)
    delta = model.apply_attempt(  # Ben has only answered Loops correctly so far
        AttemptRecord(
            id=uuid.uuid4(),
            user_id=users["ben"],
            item_id=item.id,
            concept_id="loops",
            response=wrong_with_mistake,
            correct=False,
            latency_ms=9000,
            created_at=datetime.now(UTC),
        )
    )
    messages = xai.explain_change(delta).messages
    assert any("matches a common mistake" in msg for msg in messages)
    assert any("Loops went down" in msg for msg in messages)

    feedback = StateDelta(
        user_id=users["chen"],
        source="explanation_feedback",
        source_id="x",
        trait_changes={"load_tolerance": (0.5, 0.45)},
    )
    assert xai.explain_change(feedback).messages == ["We'll keep explanations a bit shorter."]
    questionnaire = StateDelta(user_id=users["asha"], source="questionnaire", source_id="y")
    assert xai.explain_change(questionnaire).messages[0].startswith("Thanks!")


def test_no_explanation_labels_the_learner(demo) -> None:
    db, graph, model, planner, xai, users = demo
    texts = []
    for user_id in users.values():
        state = model.get_state(user_id)
        rec = planner.next_step(state)
        planner.choose_style(state, rec.target_concept_id)
        why = xai.why(rec.id)
        texts += [why.rationale.summary, why.rationale.alternative or "", why.style.summary]
        texts += [c.condition + c.outcome for c in why.rationale.counterfactuals]
        for subject in (*TRAIT_NAMES, "loops", "recursion-base-case"):
            belief = xai.explain_belief(user_id, subject)
            texts += [belief.summary, *belief.top_evidence]
    for text in texts:
        assert not any(phrase in text.lower() for phrase in BANNED_PHRASES), text
