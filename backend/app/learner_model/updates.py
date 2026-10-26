"""Pure update rules for explanation feedback, affect and behavioural traits
(docs/MODEL_SPEC.md §2.2 outcome, §2.3, §3, §4). No I/O."""

from datetime import timedelta

from app.contracts.explanation import ExplanationFeedbackSummary
from app.contracts.learner import TraitEstimate

# outcome y (§2.2)
FOLLOWUP_WEIGHT, CLARITY_WEIGHT, DISMISS_PENALTY = 0.6, 0.3, 0.1
# misconception suspicion (§3)
SUSPICION_STEP, SUSPICION_DECAY = 0.25, 0.5
# affect (§4)
ENGAGEMENT_ALPHA, FRUSTRATION_ALPHA = 0.2, 0.3
FAST_GUESS_MS = 3000
FATIGUE_FULL_MINUTES = 40
FATIGUE_DROP, FATIGUE_DROP_BONUS = 0.3, 0.2
SESSION_GAP = timedelta(minutes=30)
# behavioural traits (§2.3)
BEHAVIOUR_ALPHA = 0.05  # rate to use once proxies are calibrated; LearnerModel defaults to off
MIN_TRAIT_VARIANCE = 0.005


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return min(hi, max(lo, x))


def ewma(old: float, signal: float, alpha: float) -> float:
    return (1 - alpha) * old + alpha * signal


def feedback_outcome(summary: ExplanationFeedbackSummary, p_hat: float | None) -> float | None:
    """Explanation success y, or None when there is nothing informative to learn from.

    Follow-up correctness is mastery-adjusted (correct − p̂) so that a weak concept does not make
    every style look bad. Weights are renormalised over the components present; a quick dismissal
    only subtracts a small penalty from an otherwise informative outcome.
    """
    parts: list[tuple[float, float]] = []
    if summary.followup_correct is not None:
        expected = 0.5 if p_hat is None else p_hat
        parts.append((FOLLOWUP_WEIGHT, float(summary.followup_correct) - expected))
    if summary.clarity_rating is not None:
        parts.append((CLARITY_WEIGHT, (summary.clarity_rating - 3) / 2))
    if not parts:
        return None
    y = sum(w * v for w, v in parts) / sum(w for w, _ in parts)
    return y - DISMISS_PENALTY if summary.dismissed_quickly else y


def suspicion_after(suspicion: float, summary: ExplanationFeedbackSummary) -> float:
    if summary.followup_correct is True:
        return suspicion * SUSPICION_DECAY
    if summary.followup_correct is False and (summary.clarity_rating or 5) <= 2:
        return clamp(suspicion + SUSPICION_STEP)
    return suspicion


def frustration_signal(correct: bool, latency_ms: int, streak: int) -> float:
    return float(not correct and (latency_ms < FAST_GUESS_MS or streak <= -2))


def fatigue(minutes_in_session: float, recent_accuracy: float, session_accuracy: float) -> float:
    drop = FATIGUE_DROP_BONUS if session_accuracy - recent_accuracy >= FATIGUE_DROP else 0.0
    return clamp(minutes_in_session / FATIGUE_FULL_MINUTES + drop)


def persistence_proxy(previous_correct: bool, gap: timedelta) -> float | None:
    """After a wrong answer: 1 if the learner kept going in the same session, 0 if the session
    ended right there. Only defined when the previous attempt was wrong."""
    if previous_correct:
        return None
    return 0.0 if gap > SESSION_GAP else 1.0


def self_efficacy_proxy(confidence: int | None, correct: bool) -> float | None:
    """Confidence (1..5 -> 0..1) minus its miscalibration against the actual result."""
    if confidence is None:
        return None
    conf = (confidence - 1) / 4
    return clamp(conf - abs(conf - float(correct)))


def ewma_trait(
    estimate: TraitEstimate, proxy: float, alpha: float = BEHAVIOUR_ALPHA
) -> TraitEstimate:
    return TraitEstimate(
        mean=clamp(ewma(estimate.mean, proxy, alpha)),
        variance=max(MIN_TRAIT_VARIANCE, estimate.variance * (1 - alpha)),
        n_observations=estimate.n_observations + 1,
    )
