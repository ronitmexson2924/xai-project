"""Internal-consistency reliability (Cronbach's alpha) per trait."""

import numpy as np

from app.contracts.learner import TraitName
from app.psychometrics.questionnaire import QuestionnaireItem, keyed_value


def cronbach_alpha(scores: np.ndarray) -> float:
    """scores: respondents x items (already reverse-keyed). Returns NaN if undefined."""
    n_respondents, k = scores.shape
    if k < 2 or n_respondents < 2:
        return float("nan")
    item_variances = scores.var(axis=0, ddof=1).sum()
    total_variance = scores.sum(axis=1).var(ddof=1)
    if total_variance == 0:
        return float("nan")
    return float(k / (k - 1) * (1 - item_variances / total_variance))


def alpha_per_trait(
    items: list[QuestionnaireItem], responses: dict[str, dict[str, int]]
) -> dict[TraitName, tuple[float, int]]:
    """responses: user_id -> {item_id: value}. Uses only respondents who answered every item of a
    trait. Returns trait -> (alpha, number of complete respondents)."""
    result: dict[TraitName, tuple[float, int]] = {}
    for trait in sorted({i.trait for i in items}):
        trait_items = [i for i in items if i.trait == trait]
        rows = [
            [keyed_value(i, answers[i.id]) for i in trait_items]
            for answers in responses.values()
            if all(i.id in answers for i in trait_items)
        ]
        matrix = np.array(rows, dtype=float).reshape(len(rows), len(trait_items))
        result[trait] = (cronbach_alpha(matrix), len(rows))
    return result
