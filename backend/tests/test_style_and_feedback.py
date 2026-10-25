"""R5 (pure parts): outcome y, suspicion, style selection per arm, exploration, convergence."""

from collections import Counter
from uuid import uuid4

import numpy as np
import pytest

from app.contracts.explanation import ExplanationFeedbackSummary, StyleParams
from app.contracts.learner import AffectiveState, TraitEstimate
from app.learner_model import updates
from app.learner_model.bandit import ALL_STYLES, KAPPA, BanditPosterior, features, known_offset
from app.learner_model.traits import neutral_traits
from app.planner.style import EPSILON_MIN, select_style


def summary(**fields) -> ExplanationFeedbackSummary:
    base = {
        "explanation_id": uuid4(),
        "user_id": uuid4(),
        "concept_ids": ["loops"],
        "style": StyleParams(example_first=True, length="medium", depth="how"),
        "style_source": "thompson",
        "effective_dwell_ms": 20_000,
    }
    return ExplanationFeedbackSummary(**{**base, **fields})


def test_feedback_outcome() -> None:
    assert updates.feedback_outcome(summary(followup_correct=True), p_hat=0.4) == pytest.approx(0.6)
    assert updates.feedback_outcome(summary(clarity_rating=5), p_hat=None) == pytest.approx(1.0)
    both = updates.feedback_outcome(summary(followup_correct=True, clarity_rating=5), p_hat=0.5)
    assert both == pytest.approx((0.6 * 0.5 + 0.3 * 1.0) / 0.9)
    assert updates.feedback_outcome(summary(dismissed_quickly=True), p_hat=0.5) is None
    penalised = updates.feedback_outcome(summary(clarity_rating=3, dismissed_quickly=True), 0.5)
    assert penalised == pytest.approx(-0.1)


def test_misconception_suspicion_rules() -> None:
    confused = summary(followup_correct=False, clarity_rating=2)
    assert updates.suspicion_after(0.3, confused) == pytest.approx(0.55)
    assert updates.suspicion_after(0.9, confused) == 1.0
    assert updates.suspicion_after(0.6, summary(followup_correct=True)) == pytest.approx(0.3)
    assert updates.suspicion_after(0.3, summary(followup_correct=False)) == 0.3  # no clarity


def test_behavioural_proxies() -> None:
    from datetime import timedelta

    assert updates.persistence_proxy(False, timedelta(minutes=2)) == 1.0
    assert updates.persistence_proxy(False, timedelta(hours=3)) == 0.0
    assert updates.persistence_proxy(True, timedelta(minutes=2)) is None
    assert updates.self_efficacy_proxy(5, True) == 1.0
    assert updates.self_efficacy_proxy(5, False) == 0.0  # confident and wrong
    assert updates.self_efficacy_proxy(None, True) is None
    moved = updates.ewma_trait(TraitEstimate(mean=0.5, variance=0.04), 1.0)
    assert moved.mean == pytest.approx(0.525) and moved.variance < 0.04


def _posterior(abs_: float = 0.5, load: float = 0.5, depth: float = 0.5) -> BanditPosterior:
    traits = neutral_traits().traits
    traits["abstraction_preference"] = TraitEstimate(mean=abs_, variance=0.04)
    traits["load_tolerance"] = TraitEstimate(mean=load, variance=0.04)
    traits["depth_preference"] = TraitEstimate(mean=depth, variance=0.04)
    return BanditPosterior.from_trait_priors(traits)


def test_generic_and_static_arms() -> None:
    rng = np.random.default_rng(0)
    traits, affect = neutral_traits(), AffectiveState()
    style, source = select_style("generic", traits, affect, _posterior(0.9, 0.9, 0.9), True, rng)
    assert source == "generic"
    assert (style.example_first, style.length, style.depth, style.tone) == (
        True,
        "medium",
        "how",
        "neutral",
    )

    style, source = select_style(
        "static_personalized", traits, affect, _posterior(0.9, 0.1, 0.9), True, rng
    )
    assert source == "trait_mapped"
    assert (style.example_first, style.length, style.depth) == (False, "short", "why")
    assert style.include_diagram is False  # diagrams accompany example-first explanations only


def test_affect_constraints_and_tone() -> None:
    rng = np.random.default_rng(0)
    traits = neutral_traits()
    traits.traits["self_efficacy"] = TraitEstimate(mean=0.2, variance=0.04)
    tired = AffectiveState(fatigue=0.9)
    for _ in range(50):
        style, _ = select_style("closed_loop", traits, tired, _posterior(load=0.9), False, rng)
        assert style.length == "short"
        assert style.tone == "encouraging"


def test_exploration_floor_tries_every_style() -> None:
    """Even with a very confident posterior, ~ε_min of choices explore and every style is tried."""
    confident = BanditPosterior(
        precision=np.eye(4) * 1e6, b=np.eye(4) @ np.array([0, -0.3, 0, 0.3]) * 1e6
    )
    rng = np.random.default_rng(42)
    draws = [
        select_style("closed_loop", neutral_traits(), AffectiveState(), confident, False, rng)
        for _ in range(1000)
    ]
    sources = Counter(source for _, source in draws)
    share = sources["exploration"] / 1000
    assert abs(share - EPSILON_MIN) < 2 * np.sqrt(EPSILON_MIN * (1 - EPSILON_MIN) / 1000)
    tried = {(s.example_first, s.length, s.depth) for s, _ in draws}
    assert tried == set(ALL_STYLES)


def _simulate_learner(seed: int, n: int, true_abs: float) -> float:
    rng = np.random.default_rng(seed)
    theta = np.array([0.0, KAPPA * (2 * true_abs - 1), 0.0, 0.0])
    traits = neutral_traits()
    posterior = BanditPosterior.from_trait_priors(traits.traits)
    for _ in range(n):
        style, _ = select_style("closed_loop", traits, AffectiveState(), posterior, False, rng)
        choice = (style.example_first, style.length, style.depth)
        y = theta @ features(choice) + known_offset(choice) + rng.normal(0, 0.5)
        posterior = posterior.update(choice, y)
    return posterior.reported_traits()["abstraction_preference"].mean


def test_closed_loop_recovers_example_first_preference() -> None:
    """True abstraction_preference = 0.1, neutral questionnaire, 60 explanations each.
    A single learner can be unlucky (about 6% end above 0.35), so check 50 learners."""
    estimates = np.array([_simulate_learner(seed, 60, true_abs=0.1) for seed in range(50)])
    assert estimates.mean() < 0.35
    assert (estimates < 0.35).mean() >= 0.85
