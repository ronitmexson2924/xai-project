"""Planner thresholds and the decision trace (docs/MODEL_SPEC.md §5). Shared by the planner
and the rationale builder so explanations quote exactly the thresholds the planner used."""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from app.contracts.planning import RecommendationKind
from app.contracts.reasons import ReasonEvidence

POLICY_VERSION = "planner-v1"

DIAGNOSTIC_ATTEMPTS = 8
DIAGNOSTIC_DEPTH_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 0.1, 0.35, 0.6, 0.85)
SUSPICION_THRESHOLD = 0.5
STRUGGLE_STREAK = -2  # two wrong in a row
PREREQ_WEAK = 0.6
FRONTIER_PREREQ_MIN = 0.85
MASTERED = 0.95
REVIEW_AFTER = timedelta(hours=48)
REVIEW_EVERY = 6  # when a review is due, every 6th step is a review
TARGET_P_CORRECT = 0.7

RULE_ORDER = (
    "diagnostic",
    "misconception",
    "prereq_gap",
    "review_turn",
    "frontier",
    "review",
    "fallback",
)


@dataclass(frozen=True)
class Trace:
    """One planner decision with everything needed to explain it faithfully (XAI E1/E2)."""

    rule: str  # one of RULE_ORDER
    kind: RecommendationKind
    concept_id: str
    reasons: list[ReasonEvidence]
    threshold: float | None = None
    context: dict[str, Any] = field(default_factory=dict)
