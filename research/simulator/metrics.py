"""H3 metrics over simulation records (docs/EVALUATION_PLAN.md)."""

from collections import defaultdict

import numpy as np

from app.contracts.learner import TraitName
from simulator.driver import STYLE_TRAITS, StepRecord

BEHAVIOUR_TRAITS: tuple[TraitName, ...] = ("persistence", "self_efficacy")
FALSE_PREFERENCE = 0.15  # an estimate this far from 0.5 counts as a claimed preference


def _by_learner(records: list[StepRecord], arm: str) -> dict[int, list[StepRecord]]:
    out: dict[int, list[StepRecord]] = defaultdict(list)
    for r in records:
        if r.arm == arm:
            out[r.learner].append(r)
    for steps in out.values():
        steps.sort(key=lambda r: r.step)
    return out


def recovery_curve(
    records: list[StepRecord], arm: str, traits: tuple[TraitName, ...] = STYLE_TRAITS
) -> np.ndarray:
    """Mean absolute error of the reported traits after k explanations (index k)."""
    learners = _by_learner(records, arm)
    errors = np.array(
        [
            [np.mean([abs(r.estimated[t] - r.true[t]) for t in traits]) for r in steps]
            for steps in learners.values()
        ]
    )
    return errors.mean(axis=0)


def final_error(meta: dict, records: list[StepRecord], arm: str, traits) -> tuple[float, float]:
    """Mean absolute error of the final estimates, and its standard error."""
    truth = {r.learner: r.true for r in records if r.arm == arm}
    errors = [
        np.mean([abs(est[t] - truth[i][t]) for t in traits])
        for (a, i), est in meta["final_estimates"].items()
        if a == arm
    ]
    return float(np.mean(errors)), float(np.std(errors, ddof=1) / np.sqrt(len(errors)))


def cumulative_regret(records: list[StepRecord], arm: str) -> np.ndarray:
    """Mean over learners of the cumulative (best true fit − chosen style's true fit)."""
    learners = _by_learner(records, arm)
    regret = np.array(
        [np.cumsum([r.best_fit - r.fit for r in steps]) for steps in learners.values()]
    )
    return regret.mean(axis=0)


def learning_gain(records: list[StepRecord], meta: dict, arm: str) -> np.ndarray:
    """Per learner: true fraction of concepts known at the end minus at the start."""
    learners = _by_learner(records, arm)
    return np.array(
        [
            steps[-1].mastery_fraction - meta["initial_mastery"][i]
            for i, steps in sorted(learners.items())
        ]
    )


def paired_difference(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    """Mean of a − b with a 95% normal-approximation confidence interval."""
    diff = a - b
    half = 1.96 * diff.std(ddof=1) / np.sqrt(len(diff))
    return float(diff.mean()), float(diff.mean() - half), float(diff.mean() + half)


def rate(values: list[bool | None]) -> float:
    present = [v for v in values if v is not None]
    return float(np.mean(present)) if present else float("nan")


def arm_summary(records: list[StepRecord], meta: dict, arm: str) -> dict[str, float]:
    rows = [r for r in records if r.arm == arm]
    style_mae, style_se = final_error(meta, records, arm, STYLE_TRAITS)
    behaviour_mae, _ = final_error(meta, records, arm, BEHAVIOUR_TRAITS)
    return {
        "style_mae": style_mae,
        "style_mae_se": style_se,
        "questionnaire_mae": float(recovery_curve(records, arm)[0]),
        "behaviour_mae": behaviour_mae,
        "regret_per_step": float(np.mean([r.best_fit - r.fit for r in rows])),
        "followup_accuracy": rate([r.followup_correct for r in rows]),
        "item_accuracy": rate([r.main_correct for r in rows]),
        "learning_gain": float(learning_gain(records, meta, arm).mean()),
        "exploration_share": float(np.mean([r.source == "exploration" for r in rows])),
        "non_greedy_share": float(np.mean([r.differs_from_greedy for r in rows])),
        "distinct_styles": float(
            np.mean([len({r.style for r in s}) for s in _by_learner(records, arm).values()])
        ),
    }


def false_preference_share(meta: dict, arm: str) -> tuple[float, float]:
    """For a population with no true preferences: share of (learner, style trait) estimates that
    claim a preference, and the mean distance from 0.5."""
    distances = [
        abs(est[t] - 0.5)
        for (a, _), est in meta["final_estimates"].items()
        if a == arm
        for t in STYLE_TRAITS
    ]
    return float(np.mean([d > FALSE_PREFERENCE for d in distances])), float(np.mean(distances))
