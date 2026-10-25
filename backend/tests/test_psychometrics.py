"""R3: questionnaire scoring, the bandit prior it produces, and Cronbach's alpha."""

import numpy as np
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contracts.learner import TraitEstimate
from app.db import models as m
from app.graph.content import ContentBundle
from app.graph.service import GraphSnapshot
from app.learner_model.bandit import BanditPosterior, best_style
from app.learner_model.service import LearnerModel
from app.psychometrics.questionnaire import QuestionnaireItem, score
from app.psychometrics.reliability import alpha_per_trait, cronbach_alpha
from tests.conftest import make_user


@pytest.fixture(scope="module")
def items(bundle: ContentBundle) -> list[QuestionnaireItem]:
    return bundle.questionnaire


def answers_for(items: list[QuestionnaireItem], trait_level: dict[str, int]) -> dict[str, int]:
    """Answer consistently: `level` on forward items, its mirror on reverse-scored items."""
    return {
        i.id: (6 - trait_level[i.trait] if i.reverse_scored else trait_level[i.trait])
        for i in items
        if i.trait in trait_level
    }


def test_questionnaire_has_four_items_per_trait(items: list[QuestionnaireItem]) -> None:
    assert len(items) == 20
    for trait in {i.trait for i in items}:
        assert sum(i.trait == trait for i in items) == 4


def test_reverse_scoring(items: list[QuestionnaireItem]) -> None:
    high = score(items, answers_for(items, {"persistence": 5}))
    assert high["persistence"].mean == 1.0
    # agreeing with everything (acquiescence) cancels out to the midpoint
    agree_all = score(items, {i.id: 5 for i in items if i.trait == "persistence"})
    assert agree_all["persistence"].mean == 0.5


def test_all_threes_give_neutral_means(items: list[QuestionnaireItem]) -> None:
    scores = score(items, {i.id: 3 for i in items})
    assert len(scores) == 5
    assert all(s.mean == 0.5 and s.n_answered == 4 for s in scores.values())


def test_invalid_answers_are_rejected(items: list[QuestionnaireItem]) -> None:
    with pytest.raises(ValueError, match="unknown"):
        score(items, {"nope": 3})
    with pytest.raises(ValueError, match="outside"):
        score(items, {items[0].id: 6})
    one_answer = {next(i.id for i in items if i.trait == "self_efficacy"): 4}
    assert "self_efficacy" not in score(items, one_answer)


def test_bandit_prior_reports_questionnaire_traits_and_picks_matching_style() -> None:
    def priors(abs_: float, load: float, depth: float) -> dict[str, TraitEstimate]:
        return {
            "abstraction_preference": TraitEstimate(mean=abs_, variance=0.04),
            "load_tolerance": TraitEstimate(mean=load, variance=0.04),
            "depth_preference": TraitEstimate(mean=depth, variance=0.04),
        }

    posterior = BanditPosterior.from_trait_priors(priors(0.2, 0.6, 0.8))
    reported = posterior.reported_traits()
    assert reported["abstraction_preference"].mean == pytest.approx(0.2)
    assert reported["depth_preference"].mean == pytest.approx(0.8)
    assert reported["load_tolerance"].variance == pytest.approx(0.04)
    assert best_style(posterior.mean) == (True, "medium", "why")

    assert best_style(BanditPosterior.from_trait_priors(priors(0.9, 0.1, 0.3)).mean) == (
        False,
        "short",
        "how",
    )
    assert best_style(BanditPosterior.from_trait_priors(priors(0.5, 0.9, 0.5)).mean)[1] == "long"

    restored = BanditPosterior.from_json(posterior.to_json())
    assert np.allclose(restored.mean, posterior.mean)


def test_cronbach_alpha() -> None:
    column = np.array([1, 2, 3, 4, 5], dtype=float)
    assert cronbach_alpha(np.column_stack([column] * 4)) == pytest.approx(1.0)
    # item variances 5/3 + 1/3 + 2/3 = 8/3; totals 5,7,9,11 have variance 20/3
    # alpha = 3/2 * (1 - (8/3) / (20/3)) = 0.9
    data = np.array([[1, 2, 2], [2, 2, 3], [3, 3, 3], [4, 3, 4]], dtype=float)
    assert cronbach_alpha(data) == pytest.approx(0.9)


def test_alpha_per_trait_flips_reverse_items(items: list[QuestionnaireItem]) -> None:
    responses = {f"u{level}": answers_for(items, {"persistence": level}) for level in (1, 2, 4, 5)}
    alpha, n = alpha_per_trait(items, responses)["persistence"]
    assert n == 4 and alpha == pytest.approx(1.0)


def test_init_from_questionnaire(seeded: Session, graph: GraphSnapshot) -> None:
    model = LearnerModel(seeded, graph)
    user_id = make_user(seeded)
    items = model.questionnaire_items()
    answers = answers_for(
        items,
        {
            "abstraction_preference": 1,
            "load_tolerance": 3,
            "depth_preference": 5,
            "persistence": 4,
            "self_efficacy": 2,
        },
    )
    delta = model.init_from_questionnaire(user_id, answers)

    traits = model.get_state(user_id).traits
    assert traits.version == 1
    assert traits.traits["abstraction_preference"].mean == pytest.approx(0.0)
    assert traits.traits["depth_preference"].mean == pytest.approx(1.0)
    assert traits.traits["persistence"].mean == pytest.approx(0.75)
    assert delta.trait_changes["self_efficacy"] == pytest.approx((0.5, 0.25))
    assert seeded.scalar(select(func.count()).select_from(m.QuestionnaireResponseRow)) == 20

    stored = BanditPosterior.from_json(seeded.get(m.LearnerTraitsRow, user_id).bandit)
    assert best_style(stored.mean) == (True, "medium", "why")
    assert model.init_from_questionnaire(user_id, {i.id: 3 for i in items}) == delta  # once only
