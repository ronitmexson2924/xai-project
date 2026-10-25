"""API-specific request and response schemas.

Owner: Mit. They extend the shared models in app.contracts without changing them.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.contracts.explanation import ExplanationEventIn
from app.contracts.graph import Concept, ConceptEdge
from app.contracts.learner import AttemptResult, StateDelta
from app.contracts.xai import ChangeNotice


class QuestionnaireItemOut(BaseModel):
    """What a learner sees of an item: never its trait, scoring direction or source."""

    id: str
    text: str


class QuestionnaireAnswersIn(BaseModel):
    answers: dict[str, int] = Field(
        ..., max_length=100, description="Questionnaire item id -> Likert rating (1 to 5)"
    )


class StateUpdateView(BaseModel):
    id: int
    source: str
    source_id: str
    delta: StateDelta
    created_at: datetime


class GraphResponse(BaseModel):
    concepts: list[Concept]
    edges: list[ConceptEdge]


class EventBatchIn(BaseModel):
    events: list[ExplanationEventIn] = Field(..., max_length=200)


class EventBatchResponse(BaseModel):
    accepted: int
    duplicates: int


class AttemptResultOut(AttemptResult):
    """AttemptResult plus what the answer changed, in plain language (XAI E5)."""

    change: ChangeNotice | None = None
    feedback_change: ChangeNotice | None = None  # set when a micro-check closed an explanation


class AdminMetricsResponse(BaseModel):
    total_users: int
    consented_users: int
    arm_distribution: dict[str, int]
    total_attempts: int
    total_explanations: int
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    source_mix: dict[str, int]
    clarity_distribution: dict[int, int]
    avg_dwell_ms: float | None
