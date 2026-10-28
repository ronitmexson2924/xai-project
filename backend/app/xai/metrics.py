"""How much to trust an explanation: agreement between methods and per-method quality.

- Agreement: Spearman rank correlation of two methods' attributions over all features, and the
  overlap of their top-k features (Jaccard). High values mean the methods tell the same story.
- DiCE quality (Mothilal et al., 2020, §4): validity (share of the requested counterfactuals that
  are unique and really flip the prediction), proximity (mean distance from the learner, in units of
  each feature's typical spread), sparsity (mean number of features changed) and diversity (mean
  distance between the counterfactuals themselves).
"""

from itertools import combinations

import numpy as np

from app.ml.explain import DECISION, Counterfactual, spearman


def top_k_overlap(a: np.ndarray, b: np.ndarray, k: int = 5) -> float:
    """Jaccard overlap of the k features with the largest absolute attribution in a and in b."""
    k = min(k, len(a))
    top_a = set(np.argsort(-np.abs(a))[:k])
    top_b = set(np.argsort(-np.abs(b))[:k])
    return len(top_a & top_b) / len(top_a | top_b)


def agreement(values: dict[str, np.ndarray], k: int = 5) -> list[tuple[str, float, float]]:
    """(pair, Spearman rho, top-k overlap) for every pair of methods that produced values."""
    return [
        (f"{a}~{b}", spearman(values[a], values[b]), top_k_overlap(values[a], values[b], k))
        for a, b in combinations(values, 2)
    ]


def agreement_word(rho: float) -> str:
    return (
        "agree closely"
        if rho >= 0.85
        else "broadly agree"
        if rho >= 0.7
        else "partly agree"
        if rho >= 0.4
        else "disagree"
    )


def dice_quality(
    x: np.ndarray,
    p_now: float,
    found: list[Counterfactual],
    requested: int,
    scale: np.ndarray,
) -> dict[str, float | int | None]:
    """DiCE's own quality measures for the counterfactuals found for input x (prediction p_now)."""
    flipped = [cf for cf in found if (cf.p_correct >= DECISION) != (p_now >= DECISION)]
    if not flipped:
        return {
            "requested": requested,
            "found": 0,
            "validity": 0.0,
            "proximity": None,
            "sparsity": None,
            "diversity": None,
        }
    distances = [float(np.sum(np.abs(cf.x - x) / scale)) for cf in flipped]
    pairwise = [float(np.sum(np.abs(a.x - b.x) / scale)) for a, b in combinations(flipped, 2)]
    return {
        "requested": requested,
        "found": len(flipped),
        "validity": len(flipped) / requested,
        "proximity": float(np.mean(distances)),
        "sparsity": float(np.mean([len(cf.changes) for cf in flipped])),
        "diversity": float(np.mean(pairwise)) if pairwise else None,
    }
