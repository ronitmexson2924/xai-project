"""R2: BKT math against hand-computed values (docs/MODEL_SPEC.md §1)."""

import pytest

from app.contracts.graph import Item
from app.learner_model import bkt


@pytest.mark.parametrize(
    ("mastery", "correct", "guess", "expected"),
    [
        # 0.2*0.9 / (0.18 + 0.8*0.2) = 0.529412 -> + 0.470588*0.15 = 0.6
        (0.2, True, 0.2, 0.6),
        # 0.5*0.1 / (0.05 + 0.5*0.8) = 0.111111 -> + 0.888889*0.15 = 0.244444
        (0.5, False, 0.2, 0.244444),
        # MCQ with 4 options: 0.81 / (0.81 + 0.1*0.25) = 0.970060 -> + 0.029940*0.15 = 0.974551
        (0.9, True, 0.25, 0.974551),
    ],
)
def test_update_matches_hand_computation(
    mastery: float, correct: bool, guess: float, expected: float
) -> None:
    assert bkt.update(mastery, correct, slip=0.1, guess=guess, p_learn=0.15) == pytest.approx(
        expected, abs=1e-6
    )


def test_predict_correct() -> None:
    assert bkt.predict_correct(0.2, slip=0.1, guess=0.2) == pytest.approx(0.34)


def test_guess_uses_option_count_for_mcq() -> None:
    mcq = Item(
        id="x", concept_id="c", kind="mcq", stem="?", options=["a", "b", "c", "d"], answer="a"
    )
    short = Item(id="y", concept_id="c", kind="short", stem="?", answer="a")
    assert bkt.guess_for(mcq) == 0.25
    assert bkt.guess_for(short) == bkt.DEFAULT_PARAMS.p_guess


def test_prior_depends_on_prerequisites() -> None:
    assert bkt.prior([]) == pytest.approx(0.2)
    assert bkt.prior([1.0]) == pytest.approx(0.3)
    assert bkt.prior([0.0, 0.0]) == pytest.approx(0.1)
    assert bkt.PRIOR_MIN <= bkt.prior([0.0], bkt.BKTParams(p_init=0.01))


def test_effective_mastery_fills_unattempted_concepts(graph) -> None:
    eff = bkt.effective_mastery(graph, {"loops": 0.95})
    assert eff["loops"] == 0.95
    assert len(eff) == len(graph.concept_ids)
    # strong prerequisite mastery raises a dependent's prior above the base prior
    weak = bkt.effective_mastery(graph, {"loops": 0.05})
    assert eff["array-traversal"] > weak["array-traversal"]
