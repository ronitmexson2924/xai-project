"""Explanation style selection per experiment arm (docs/MODEL_SPEC.md §2.2). No I/O."""

import numpy as np

from app.contracts.explanation import StyleParams, StyleSource
from app.contracts.learner import AffectiveState, ExperimentArm, LearnerTraits
from app.learner_model.bandit import ALL_STYLES, BanditPosterior, StyleChoice, best_style

EPSILON_MIN = 0.1  # minimum exploration rate in the closed loop (tune)
FATIGUE_SHORT_ONLY = 0.7
LOW_SELF_EFFICACY = 0.4
HIGH_FRUSTRATION = 0.6

GENERIC_STYLE: StyleChoice = (True, "medium", "how")


def candidates(affect: AffectiveState) -> tuple[StyleChoice, ...]:
    if affect.fatigue > FATIGUE_SHORT_ONLY:
        return tuple(s for s in ALL_STYLES if s[1] == "short")
    return ALL_STYLES


def select_style(
    arm: ExperimentArm,
    traits: LearnerTraits,
    affect: AffectiveState,
    posterior: BanditPosterior,
    card_has_diagram: bool,
    rng: np.random.Generator,
    epsilon: float = EPSILON_MIN,
) -> tuple[StyleParams, StyleSource]:
    """generic: one fixed style. static_personalized: argmax under the posterior mean (which never
    moves, since that arm gets no trait updates). closed_loop: Thompson sampling with an
    exploration floor. Both personalised arms apply the affect constraints and tone rule."""
    if arm == "generic":
        example_first, length, depth = GENERIC_STYLE
        style = StyleParams(
            example_first=example_first,
            length=length,
            depth=depth,
            tone="neutral",
            include_diagram=card_has_diagram,
        )
        return style, "generic"

    allowed = candidates(affect)
    source: StyleSource
    if arm == "static_personalized":
        choice, source = best_style(posterior.mean, allowed), "trait_mapped"
    elif rng.random() < epsilon:
        choice, source = allowed[rng.integers(len(allowed))], "exploration"
    else:
        choice, source = best_style(posterior.sample(rng), allowed), "thompson"

    example_first, length, depth = choice
    encouraging = (
        traits.traits["self_efficacy"].mean < LOW_SELF_EFFICACY
        or affect.frustration > HIGH_FRUSTRATION
    )
    style = StyleParams(
        example_first=example_first,
        length=length,
        depth=depth,
        tone="encouraging" if encouraging else "neutral",
        include_diagram=card_has_diagram and example_first,
    )
    return style, source
