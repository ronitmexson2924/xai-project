"""Modules B and C. StyleParams is chosen by Ronit's planner and rendered by Mit's explainer;
ExplanationFeedbackSummary is produced by Mit's telemetry and consumed by Ronit's learner model."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.contracts.reasons import ReasonEvidence

Length = Literal["short", "medium", "long"]
Depth = Literal["how", "why"]
Tone = Literal["encouraging", "neutral"]
StyleSource = Literal["generic", "trait_mapped", "thompson", "exploration"]
ExplanationSource = Literal["precomputed", "llm", "template"]


class StyleParams(BaseModel):
    example_first: bool
    length: Length
    depth: Depth
    tone: Tone = "neutral"
    include_diagram: bool = False

    def variant_key(self) -> str:
        """Key of the LLM-generated variant (tone and diagram are applied by the wrapper)."""
        return f"ex{int(self.example_first)}-{self.length}-{self.depth}"


class ExplanationRequest(BaseModel):
    user_id: UUID
    recommendation_id: UUID
    concept_ids: list[str] = Field(min_length=1)
    reasons: list[ReasonEvidence]
    style: StyleParams
    style_source: StyleSource
    followup_item_id: str | None = None


class Explanation(BaseModel):
    id: UUID
    recommendation_id: UUID
    user_id: UUID
    concept_ids: list[str]
    style: StyleParams
    style_source: StyleSource
    body_markdown: str
    source: ExplanationSource
    prompt_version: str
    model: str | None = None
    followup_item_id: str | None = None
    latency_ms: int = 0


ExplanationEventType = Literal[
    "shown",
    "expanded",
    "collapsed",
    "replayed",
    "hidden",
    "visible",
    "clarity_rated",  # payload: {"rating": 1..5}
    "followup_answered",  # payload: {"item_id": str, "correct": bool}
    "dismissed",
]


class ExplanationEventIn(BaseModel):
    idempotency_key: UUID
    type: ExplanationEventType
    client_ts: datetime
    payload: dict[str, Any] = {}


class ExplanationEventBatch(BaseModel):
    events: list[ExplanationEventIn] = Field(max_length=200)


class ExplanationFeedbackSummary(BaseModel):
    """One explanation's interaction, condensed. The interface between Mit (C capture) and
    Ronit (C update rules)."""

    explanation_id: UUID
    user_id: UUID
    concept_ids: list[str]
    style: StyleParams
    style_source: StyleSource
    effective_dwell_ms: int = Field(ge=0)  # visible time only
    expanded: bool = False
    replays: int = 0
    clarity_rating: int | None = Field(default=None, ge=1, le=5)
    followup_correct: bool | None = None
    dismissed_quickly: bool = False  # visible < 3 s and no other interaction
