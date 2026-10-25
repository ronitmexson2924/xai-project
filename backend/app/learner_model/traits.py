"""Trait-vector helpers (docs/MODEL_SPEC.md §2)."""

from app.contracts.learner import TRAIT_NAMES, LearnerTraits, TraitEstimate

PRIOR_VARIANCE = 0.04  # SD 0.2: short scales are noisy (tune)


def neutral_traits() -> LearnerTraits:
    """Traits before any evidence: every mean 0.5 with prior variance."""
    return LearnerTraits(
        traits={t: TraitEstimate(mean=0.5, variance=PRIOR_VARIANCE) for t in TRAIT_NAMES}
    )
