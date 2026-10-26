"""The performance model and its explanations (SHAP, LIME, LRP, DiCE).

Most tests use small hand-built networks whose correct explanation is known, and check the
property each method promises in its paper: SHAP's additivity, LRP's conservation, LIME's
recovery of a linear model, DiCE's valid, actionable, diverse counterfactuals.
"""

import uuid
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from sqlalchemy.orm import Session

from app.contracts.learner import AttemptRecord
from app.db import models as m
from app.graph.service import GraphSnapshot
from app.learner_model.service import LearnerModel
from app.ml import explain
from app.ml.features import FEATURE_NAMES, FEATURES, N_FEATURES, replay
from app.ml.model import ARTIFACT, PerformanceModel, load
from tests.conftest import make_user

LOW = np.array([f.low for f in FEATURES], dtype=float)
HIGH = np.array([f.high for f in FEATURES], dtype=float)
MASTERY = FEATURE_NAMES.index("mastery")


def _background(n: int = 120, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).uniform(LOW, HIGH, (n, N_FEATURES))


def _model(weights: list[np.ndarray], biases: list[np.ndarray]) -> PerformanceModel:
    return PerformanceModel(
        mean=(LOW + HIGH) / 2,
        scale=(HIGH - LOW) / 4,
        weights=weights,
        biases=biases,
        background=_background(),
    )


def only_mastery_matters() -> PerformanceModel:
    """logit = 3 * standardised mastery: no other feature has any effect."""
    w = np.zeros((N_FEATURES, 1))
    w[MASTERY, 0] = 3.0
    return _model([w], [np.zeros(1)])


def small_network(seed: int = 1, bias: bool = True) -> PerformanceModel:
    rng = np.random.default_rng(seed)
    sizes = (N_FEATURES, 8, 4, 1)
    weights = [rng.normal(0, 0.6, (a, b)) for a, b in zip(sizes, sizes[1:], strict=False)]
    biases = [rng.normal(0, 0.2, b) if bias else np.zeros(b) for b in sizes[1:]]
    return _model(weights, biases)


def learner(mastery: float = 0.3, **overrides: float) -> np.ndarray:
    x = (LOW + HIGH) / 2
    x[MASTERY] = mastery
    for name, value in overrides.items():
        x[FEATURE_NAMES.index(name)] = value
    return x


# --- the model ------------------------------------------------------------------------------


def test_model_round_trips_through_json_and_gradients_are_right() -> None:
    model = small_network()
    again = PerformanceModel.from_json(model.to_json())
    xs = _background(20, seed=3)
    assert np.allclose(model.predict_proba(xs), again.predict_proba(xs))
    x = learner()
    numeric = np.array(
        [(model.logit(x + e)[0] - model.logit(x - e)[0]) / 2e-5 for e in np.eye(N_FEATURES) * 1e-5]
    )
    assert np.allclose(model.grad_logit(x), numeric, atol=1e-4)


def test_a_model_for_other_features_is_refused() -> None:
    data = small_network().to_json()
    data["features"] = data["features"][:-1]
    with pytest.raises(ValueError, match="retrain"):
        PerformanceModel.from_json(data)


def test_the_shipped_model_loads_and_documents_itself() -> None:
    model = load(ARTIFACT)
    p = model.predict_proba(model.background[:5])
    assert ((p > 0) & (p < 1)).all()
    card = model.card
    assert {"neural network (this model)", "BKT (the learner model)"} <= set(card["test_metrics"])
    assert set(card["global_importance"]["shap"]) == set(FEATURE_NAMES)


# --- SHAP -----------------------------------------------------------------------------------


def test_shap_is_additive_and_ignores_features_the_model_ignores() -> None:
    for model in (small_network(), only_mastery_matters()):
        a = explain.shap_attribution(model, learner(0.8))
        assert abs(a.residual) < 1e-6  # base + sum of contributions = the prediction
    a = explain.shap_attribution(only_mastery_matters(), learner(0.8))
    others = np.delete(a.values, MASTERY)
    assert a.values[MASTERY] > 0.1 and np.abs(others).max() < 1e-9


# --- LIME -----------------------------------------------------------------------------------


def test_lime_recovers_a_model_that_is_nearly_linear() -> None:
    # linear in log-odds, so only nearly linear in probability (the sigmoid bends): LIME's R²
    # reports exactly that, which is why the UI shows it
    a = explain.lime_attribution(only_mastery_matters(), learner(0.55))
    assert a.fidelity is not None and a.fidelity > 0.8
    assert int(np.argmax(np.abs(a.values))) == MASTERY
    assert abs(a.residual) < 1e-6


# --- LRP ------------------------------------------------------------------------------------


def test_lrp_conserves_the_output() -> None:
    no_bias = small_network(bias=False)
    a = explain.lrp_attribution(no_bias, learner(0.7), eps=1e-9)
    assert a.values.sum() == pytest.approx(a.output, abs=1e-6)  # all relevance reaches the inputs
    with_bias = explain.lrp_attribution(small_network(), learner(0.7), eps=1e-9)
    assert abs(with_bias.residual) < 1e-6  # inputs + what biases absorbed = the logit


def test_lrp_on_a_linear_model_is_weight_times_input() -> None:
    model = only_mastery_matters()
    x = learner(0.9)
    a = explain.lrp_attribution(model, x, eps=1e-12)
    expected = 3.0 * model.standardise(x)[MASTERY]
    assert a.values[MASTERY] == pytest.approx(expected)
    assert np.abs(np.delete(a.values, MASTERY)).max() == 0


# --- DiCE -----------------------------------------------------------------------------------


@pytest.mark.parametrize("mastery", [0.15, 0.9])
def test_dice_counterfactuals_flip_the_prediction_realistically(mastery: float) -> None:
    model = small_network(seed=4)
    x = learner(mastery, attempts=6)
    p = float(model.predict_proba(x)[0])
    found = explain.counterfactuals(model, x)
    assert found, "no counterfactual found"
    immutable = [j for j, f in enumerate(FEATURES) if not f.actionable]
    for cf in found:
        assert (cf.p_correct >= 0.5) != (p >= 0.5)  # valid: the prediction really flips
        assert np.allclose(cf.x[immutable], x[immutable])  # only actionable features move
        assert ((cf.x >= LOW - 1e-9) & (cf.x <= HIGH + 1e-9)).all()  # plausible values
        assert cf.x[FEATURE_NAMES.index("attempts")] >= 6  # practice cannot be undone
        assert set(cf.changes) <= {f.name for f in FEATURES if f.actionable}
    assert len({tuple(sorted(cf.changes)) for cf in found}) == len(found) or len(found) == 1


def _only(feature: str, weight: float) -> PerformanceModel:
    w = np.zeros((N_FEATURES, 1))
    w[FEATURE_NAMES.index(feature), 0] = weight
    return _model([w], [np.zeros(1)])


def test_dice_never_suggests_acquiring_a_misconception() -> None:
    # a model that (wrongly, but faithfully to its data) links a flagged misconception to success
    model = _only("misconception", 3.0)
    x = learner(misconception=0)
    assert model.predict_proba(x)[0] < 0.5
    for cf in explain.counterfactuals(model, x):
        assert cf.x[FEATURE_NAMES.index("misconception")] == 0  # never "get a misconception"


def test_dice_may_suggest_clearing_a_misconception() -> None:
    found = explain.counterfactuals(_only("misconception", -3.0), learner(misconception=1))
    assert found and all(cf.changes == {"misconception": (1.0, 0.0)} for cf in found)


def test_dice_on_a_mastery_only_model_changes_mastery() -> None:
    found = explain.counterfactuals(only_mastery_matters(), learner(0.2))
    assert found and all(set(cf.changes) == {"mastery"} for cf in found)  # sparse: nothing else


# --- together -------------------------------------------------------------------------------


def test_all_methods_agree_when_the_answer_is_obvious() -> None:
    e = explain.explain(only_mastery_matters(), learner(0.85))
    for name, a in e.attributions.items():
        assert int(np.argmax(np.abs(a.values))) == MASTERY, name
    assert all(-1 <= v <= 1 for v in e.agreement.values())


# --- features: replayed from the logs, consistent with the learner model ----------------------


def test_replay_reproduces_what_the_learner_model_believed(
    seeded: Session, graph: GraphSnapshot
) -> None:
    model = LearnerModel(seeded, graph)
    user_id = make_user(seeded)
    t0 = datetime(2026, 1, 5, 9, tzinfo=UTC)
    answers = [("4", False), ("3", True), ("3", True), ("4", False)]
    deltas = []
    for n, (response, correct) in enumerate(answers):
        deltas.append(
            model.apply_attempt(
                AttemptRecord(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    item_id="t-loops-mcq",
                    concept_id="loops",
                    response=response,
                    correct=correct,
                    latency_ms=5000,
                    created_at=t0 + timedelta(hours=n),
                )
            )
        )
    state, rows = replay(seeded, graph, user_id)

    assert [r.y for r in rows] == [0, 1, 1, 0]
    col = {name: i for i, name in enumerate(FEATURE_NAMES)}
    for row, delta in zip(rows, deltas, strict=True):  # mastery as the model believed it then
        assert row.x[col["mastery"]] == pytest.approx(delta.mastery_changes["loops"][0])
    assert [r.x[col["attempts"]] for r in rows] == [0, 1, 2, 3]
    assert [r.x[col["misconception"]] for r in rows] == [0, 1, 1, 0]  # flagged, then cleared
    assert rows[3].x[col["streak"]] == 2
    assert rows[1].x[col["days_since_practice"]] == pytest.approx(1 / 24)

    # the live features for the next answer match the learner model's current state
    live = state.features(graph.get_item("t-loops-mcq"), t0 + timedelta(days=1))
    current = seeded.get(m.LearnerConceptStateRow, (user_id, "loops"))
    assert live[col["mastery"]] == pytest.approx(current.p_mastery)
    assert live[col["streak"]] == current.streak == -1
    assert live[col["attempts"]] == current.n_attempts == 4
