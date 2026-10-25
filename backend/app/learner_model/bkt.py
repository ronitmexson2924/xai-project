"""Bayesian Knowledge Tracing (docs/MODEL_SPEC.md §1). Pure functions, no I/O."""

from dataclasses import dataclass

from app.contracts.graph import Item
from app.graph.service import GraphSnapshot


@dataclass(frozen=True)
class BKTParams:
    p_init: float = 0.2  # base prior before prerequisite adjustment (tune)
    p_learn: float = 0.15  # t (tune)
    p_slip: float = 0.1  # s (tune)
    p_guess: float = 0.2  # g for non-MCQ items (tune); MCQ uses 1/k


DEFAULT_PARAMS = BKTParams()
PRIOR_MIN, PRIOR_MAX = 0.05, 0.6


def guess_for(item: Item, params: BKTParams = DEFAULT_PARAMS) -> float:
    if item.kind == "mcq" and len(item.options) >= 2:
        return 1.0 / len(item.options)
    return params.p_guess


def predict_correct(mastery: float, slip: float, guess: float) -> float:
    return mastery * (1 - slip) + (1 - mastery) * guess


def observe(mastery: float, correct: bool, slip: float, guess: float) -> float:
    """Posterior P(mastered) after one observation, before the learning transition."""
    if correct:
        num = mastery * (1 - slip)
        den = num + (1 - mastery) * guess
    else:
        num = mastery * slip
        den = num + (1 - mastery) * (1 - guess)
    return num / den if den > 0 else mastery


def transition(mastery: float, p_learn: float) -> float:
    return mastery + (1 - mastery) * p_learn


def update(mastery: float, correct: bool, slip: float, guess: float, p_learn: float) -> float:
    return transition(observe(mastery, correct, slip, guess), p_learn)


def prior(prereq_masteries: list[float], params: BKTParams = DEFAULT_PARAMS) -> float:
    """Prerequisite-informed prior for a concept the learner has never attempted."""
    if not prereq_masteries:
        return params.p_init
    mean = sum(prereq_masteries) / len(prereq_masteries)
    return min(PRIOR_MAX, max(PRIOR_MIN, params.p_init * (0.5 + mean)))


def effective_mastery(
    graph: GraphSnapshot, known: dict[str, float], params: BKTParams = DEFAULT_PARAMS
) -> dict[str, float]:
    """Mastery for every concept: the stored value if attempted, otherwise the prior computed from
    (effective) prerequisite mastery, in topological order."""
    result: dict[str, float] = {}
    for concept_id in graph.topological_order:
        if concept_id in known:
            result[concept_id] = known[concept_id]
        else:
            result[concept_id] = prior([result[p] for p in graph.prerequisites(concept_id)], params)
    return result
