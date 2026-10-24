"""Unified learner state (Module A). Ronit produces; Mit displays."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

TraitName = Literal[
    "abstraction_preference",  # 0 = example-first, 1 = rule-first
    "load_tolerance",  # 0 = short/chunked, 1 = dense/long
    "depth_preference",  # 0 = "how", 1 = "why"
    "persistence",
    "self_efficacy",
]
TRAIT_NAMES: tuple[TraitName, ...] = (
    "abstraction_preference",
    "load_tolerance",
    "depth_preference",
    "persistence",
    "self_efficacy",
)

ExperimentArm = Literal["generic", "static_personalized", "closed_loop"]


class TraitEstimate(BaseModel):
    mean: float = Field(ge=0.0, le=1.0)
    variance: float = Field(ge=0.0)
    n_observations: int = 0


class LearnerTraits(BaseModel):
    traits: dict[TraitName, TraitEstimate]
    version: int = 0


class ConceptMastery(BaseModel):
    concept_id: str
    p_mastery: float = Field(ge=0.0, le=1.0)
    n_attempts: int = 0
    misconception_ids: list[str] = []
    misconception_suspicion: float = Field(default=0.0, ge=0.0, le=1.0)


class AffectiveState(BaseModel):
    engagement: float = Field(default=0.5, ge=0.0, le=1.0)
    frustration: float = Field(default=0.0, ge=0.0, le=1.0)
    fatigue: float = Field(default=0.0, ge=0.0, le=1.0)


class LearnerState(BaseModel):
    user_id: UUID
    arm: ExperimentArm
    mastery: dict[str, ConceptMastery]  # concept_id -> mastery; missing = prior
    traits: LearnerTraits
    affect: AffectiveState = AffectiveState()
    total_attempts: int = 0


class AttemptIn(BaseModel):
    """Body of POST /attempts."""

    item_id: str
    response: str
    latency_ms: int = Field(ge=0)
    hints_used: int = 0
    confidence: int | None = Field(default=None, ge=1, le=5)
    recommendation_id: UUID | None = None
    explanation_id: UUID | None = None  # set when the item is a micro-check


class AttemptRecord(AttemptIn):
    """An attempt after grading, as passed to LearnerModelService.apply_attempt."""

    id: UUID
    user_id: UUID
    concept_id: str
    correct: bool
    created_at: datetime


StateUpdateSource = Literal["attempt", "explanation_feedback", "questionnaire"]


class StateDelta(BaseModel):
    """What one update changed; stored in `state_updates` for audit and 'why we think this'."""

    user_id: UUID
    source: StateUpdateSource
    source_id: str
    mastery_changes: dict[str, tuple[float, float]] = {}  # concept_id -> (before, after)
    trait_changes: dict[TraitName, tuple[float, float]] = {}  # trait -> (before mean, after mean)
    notes: list[str] = []


class AttemptResult(BaseModel):
    """Response of POST /attempts."""

    correct: bool
    correct_answer: str | None = None
    delta: StateDelta
