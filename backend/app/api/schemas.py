"""API-specific request and response schemas.

Owner: Mit.
Builds on the domain models in app.contracts. Request bodies here are stricter than the contracts
(length and range limits, unknown fields rejected): they are the trust boundary.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.explanation import ExplanationEventIn, ExplanationFeedbackSummary
from app.contracts.graph import Concept, ConceptEdge, PublicItem
from app.contracts.learner import AttemptIn, AttemptResult, StateDelta
from app.contracts.xai import ChangeNotice

MAX_RESPONSE_CHARS = 2000
MAX_EVENTS_PER_BATCH = 100
MAX_PAYLOAD_KEYS = 8
# events a learner's browser may send; "followup_answered" is recorded by the server when the
# micro-check is graded, so a client cannot claim a correct answer it never gave
CLIENT_EVENT_TYPES = {
    "shown",
    "expanded",
    "collapsed",
    "replayed",
    "hidden",
    "visible",
    "clarity_rated",
    "dismissed",
    "why_opened",
    "why_rated",
}

TestPhase = Literal["pretest", "posttest"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionnaireItem(BaseModel):
    id: str
    trait: str
    text: str
    reverse_scored: bool = False
    source: str = ""


class QuestionnaireAnswersIn(Strict):
    answers: dict[str, int] = Field(
        ..., max_length=100, description="Map of questionnaire item ID to Likert rating (1 to 5)"
    )


class StateUpdateView(BaseModel):
    id: int
    user_id: UUID
    source: str
    source_id: str
    delta: StateDelta
    created_at: datetime


class GraphResponse(BaseModel):
    concepts: list[Concept]
    edges: list[ConceptEdge]


class AttemptBody(AttemptIn):
    """POST /attempts. A practice answer must name the recommendation it answers."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1, max_length=200)
    response: str = Field(max_length=MAX_RESPONSE_CHARS)
    latency_ms: int = Field(ge=0, le=24 * 3600 * 1000)
    hints_used: int = Field(default=0, ge=0, le=20)
    recommendation_id: UUID


class AttemptResultOut(AttemptResult):
    """AttemptResult plus the XAI E5 notice of what the answer changed."""

    change: ChangeNotice | None = None


class EventIn(ExplanationEventIn):
    model_config = ConfigDict(extra="forbid")

    @field_validator("type")
    @classmethod
    def client_may_send(cls, value: str) -> str:
        if value not in CLIENT_EVENT_TYPES:
            raise ValueError(f"event type {value!r} is recorded by the server")
        return value

    @field_validator("payload")
    @classmethod
    def small_flat_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > MAX_PAYLOAD_KEYS:
            raise ValueError("payload has too many keys")
        for key, v in value.items():
            if len(key) > 40 or not isinstance(v, str | int | float | bool | None):
                raise ValueError("payload values must be short scalars")
            if isinstance(v, str) and len(v) > 200:
                raise ValueError("payload strings must be at most 200 characters")
        return value

    @model_validator(mode="after")
    def payload_matches_type(self) -> "EventIn":
        if self.type == "clarity_rated":
            rating = self.payload.get("rating")
            if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5:
                raise ValueError("clarity_rated needs payload.rating between 1 and 5")
        if self.type == "why_rated" and not isinstance(self.payload.get("helpful"), bool):
            raise ValueError("why_rated needs payload.helpful true or false")
        return self


class EventBatchIn(Strict):
    events: list[EventIn] = Field(..., min_length=1, max_length=MAX_EVENTS_PER_BATCH)


class EventBatchResponse(BaseModel):
    accepted: int
    duplicates: int


class FeedbackOut(ExplanationFeedbackSummary):
    """Response of POST /explanations/{id}/close: the summary and what it changed (XAI E5)."""

    change: ChangeNotice | None = None


class TestOut(BaseModel):
    phase: TestPhase
    items: list[PublicItem]
    submitted: bool


class TestAnswersIn(Strict):
    answers: dict[str, str] = Field(..., min_length=1, max_length=50)

    @field_validator("answers")
    @classmethod
    def short_answers(cls, value: dict[str, str]) -> dict[str, str]:
        if any(len(k) > 200 or len(v) > MAX_RESPONSE_CHARS for k, v in value.items()):
            raise ValueError("answer too long")
        return value


class TestSubmitted(BaseModel):
    phase: TestPhase
    answered: int


class AdminMetricsResponse(BaseModel):
    """Every number is measured from the database; nothing here is a placeholder."""

    total_users: int
    consented_users: int
    arm_distribution: dict[str, int]
    total_attempts: int
    total_explanations: int
    p50_explanation_latency_ms: float | None
    p95_explanation_latency_ms: float | None
    source_mix: dict[str, int]
    clarity_distribution: dict[int, int]
    avg_dwell_ms: float | None
    pretest_submissions: int
    posttest_submissions: int
