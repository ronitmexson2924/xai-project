"""Bayesian linear bandit over explanation styles (docs/MODEL_SPEC.md §2.2). Pure math, no I/O.

The three style-identifiable traits are the learner-specific coefficients of a linear model of
explanation success:

    y = θ0 + θ_abs·x_abs + θ_load·x_load + θ_depth·x_depth − c·x_load² + ε,   ε ~ N(0, σ²)

θ is measured in trait units: θ_k = κ(2τ_k − 1) for a trait τ_k in [0, 1], so the questionnaire
prior maps to exactly the questionnaire score and the posterior maps back to a reported trait.
The fixed curvature c makes `medium` length optimal unless the load preference is strong.
"""

from dataclasses import dataclass
from itertools import product
from typing import Any

import numpy as np

from app.contracts.explanation import Depth, Length
from app.contracts.learner import TraitEstimate, TraitName

KAPPA = 0.3  # largest effect of one style feature on y, in y units (tune)
LOAD_CURVATURE = KAPPA / 2  # medium wins while |2·τ_load − 1| < 0.5, i.e. 0.25 < τ_load < 0.75
NOISE_VAR = 0.25  # σ² of y (tune)
INTERCEPT_PRIOR_VAR = 0.25
MAX_TRAIT_VARIANCE = 0.25  # variance of a uniform-ish belief on [0, 1]

STYLE_TRAITS: tuple[TraitName, ...] = (
    "abstraction_preference",
    "load_tolerance",
    "depth_preference",
)
LENGTH_X: dict[Length, int] = {"short": -1, "medium": 0, "long": 1}

StyleChoice = tuple[bool, Length, Depth]  # (example_first, length, depth)
ALL_STYLES: tuple[StyleChoice, ...] = tuple(
    product((True, False), ("short", "medium", "long"), ("how", "why"))
)


def features(style: StyleChoice) -> np.ndarray:
    example_first, length, depth = style
    return np.array(
        [
            1.0,
            -1.0 if example_first else 1.0,
            float(LENGTH_X[length]),
            1.0 if depth == "why" else -1.0,
        ]
    )


def known_offset(style: StyleChoice) -> float:
    """The fixed (non-learned) part of the expected outcome."""
    return -LOAD_CURVATURE * LENGTH_X[style[1]] ** 2


def predicted_value(theta: np.ndarray, style: StyleChoice) -> float:
    return float(theta @ features(style)) + known_offset(style)


def best_style(theta: np.ndarray, candidates: tuple[StyleChoice, ...] = ALL_STYLES) -> StyleChoice:
    # Ties go to the earlier candidate; ALL_STYLES lists example-first and `how` first.
    return max(candidates, key=lambda s: predicted_value(theta, s))


@dataclass(frozen=True)
class BanditPosterior:
    precision: np.ndarray  # 4x4, Λ
    b: np.ndarray  # 4, so that mean = Λ⁻¹ b
    n: int = 0  # observations absorbed

    @classmethod
    def from_trait_priors(cls, priors: dict[TraitName, TraitEstimate]) -> "BanditPosterior":
        """Prior from the questionnaire-based trait estimates (one per style trait)."""
        mean = np.zeros(4)
        var = np.full(4, INTERCEPT_PRIOR_VAR)
        for k, trait in enumerate(STYLE_TRAITS, start=1):
            estimate = priors[trait]
            mean[k] = KAPPA * (2 * estimate.mean - 1)
            var[k] = 4 * KAPPA**2 * max(estimate.variance, 1e-6)
        precision = np.diag(1 / var)
        return cls(precision=precision, b=precision @ mean)

    @property
    def mean(self) -> np.ndarray:
        return np.linalg.solve(self.precision, self.b)

    @property
    def covariance(self) -> np.ndarray:
        return np.linalg.inv(self.precision)

    def update(self, style: StyleChoice, y: float) -> "BanditPosterior":
        x = features(style)
        y_learned = y - known_offset(style)
        return BanditPosterior(
            precision=self.precision + np.outer(x, x) / NOISE_VAR,
            b=self.b + x * y_learned / NOISE_VAR,
            n=self.n + 1,
        )

    def sample(self, rng: np.random.Generator) -> np.ndarray:
        return rng.multivariate_normal(self.mean, self.covariance)

    def reported_traits(self) -> dict[TraitName, TraitEstimate]:
        mean, cov = self.mean, self.covariance
        return {
            trait: TraitEstimate(
                mean=(float(np.clip(mean[k] / KAPPA, -1, 1)) + 1) / 2,
                variance=min(MAX_TRAIT_VARIANCE, float(cov[k, k]) / (4 * KAPPA**2)),
                n_observations=self.n,
            )
            for k, trait in enumerate(STYLE_TRAITS, start=1)
        }

    def to_json(self) -> dict[str, Any]:
        return {"precision": self.precision.tolist(), "b": self.b.tolist(), "n": self.n}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "BanditPosterior":
        return cls(
            precision=np.array(data["precision"], dtype=float),
            b=np.array(data["b"], dtype=float),
            n=int(data.get("n", 0)),
        )
