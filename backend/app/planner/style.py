"""Explanation style selection per experiment arm (docs/MODEL_SPEC.md §2.2). No I/O."""

import numpy as np

from app.contracts.explanation import StyleParams, StyleSource
from app.contracts.learner import AffectiveState, ExperimentArm, LearnerTraits
from app.contracts.xai import Confidence, StyleRationale
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


# --- XAI E3: why the explanation looks the way it does -------------------------------------------

P_BEST_SAMPLES = 1000
_OPENING = {True: "starts with an example", False: "starts with the general rule"}
_LENGTH = {"short": "is short", "medium": "is medium-length", "long": "is detailed"}
_DEPTH = {"how": "focuses on how to use it", "why": "focuses on why it works"}


def p_best(
    posterior: BanditPosterior,
    choice: StyleChoice,
    allowed: tuple[StyleChoice, ...],
    rng: np.random.Generator,
    samples: int = P_BEST_SAMPLES,
) -> float:
    """Posterior probability that `choice` is the best allowed style for this learner."""
    draws = rng.multivariate_normal(posterior.mean, posterior.covariance, size=samples)
    return float(np.mean([best_style(theta, allowed) == choice for theta in draws]))


def explain_style(
    style: StyleParams,
    source: StyleSource,
    posterior: BanditPosterior,
    affect: AffectiveState,
    rng: np.random.Generator,
) -> StyleRationale:
    """Learner-facing reason for a style choice, from the same posterior it was chosen with."""
    choice: StyleChoice = (style.example_first, style.length, style.depth)
    allowed = candidates(affect)
    tired = len(allowed) < len(ALL_STYLES)  # fatigue forced short: don't credit it to learning
    opening, depth = _OPENING[style.example_first], _DEPTH[style.depth]
    described = (
        f"{opening} and {depth}" if tired else f"{opening}, {_LENGTH[style.length]} and {depth}"
    )
    probability: float | None = None
    confidence: Confidence = "tentative"
    if source == "generic":
        summary = "This is the app's standard explanation style."
    elif source == "trait_mapped":
        summary = f"Based on your questionnaire answers, this explanation {described}."
    else:
        probability = p_best(posterior, choice, allowed, rng)
        n = posterior.n
        if n >= 15 and probability >= 0.6:
            confidence = "confident"
        elif n >= 5:
            confidence = "moderate"
        if source == "exploration":
            summary = (
                f"We're trying a different style this time (it {described}) to learn what works "
                "best for you. Your feedback on it helps."
            )
        elif n == 0:
            summary = (
                f"This explanation {described}. We don't have feedback from you yet, so this is "
                "a first guess that your ratings will refine."
            )
        else:
            summary = (
                f"This explanation {described}, because explanations like it have worked well "
                f"for you so far (based on {n} explanation{'s' if n != 1 else ''}; about "
                f"{round(100 * probability)}% likely to be your best "
                f"{'short ' if tired else ''}style)."
            )
    if tired:
        summary += " It's kept short because you've been studying for a while."
    return StyleRationale(source=source, summary=summary, p_best=probability, confidence=confidence)
