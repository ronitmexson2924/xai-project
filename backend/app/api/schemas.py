"""API-specific request and response schemas.

Owner: Mit.
Builds upon and references domain models from app.contracts.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.contracts.explanation import ExplanationEventIn
from app.contracts.graph import Concept, ConceptEdge
from app.contracts.learner import StateDelta


class QuestionnaireItem(BaseModel):
    id: str
    trait: str
    text: str
    reverse_scored: bool = False
    source: str = ""


class QuestionnaireAnswersIn(BaseModel):
    answers: dict[str, int] = Field(
        ...,
        description="Map of questionnaire item ID to likert rating (1 to 5)",
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


class EventBatchIn(BaseModel):
    events: list[ExplanationEventIn] = Field(
        ...,
        description="Batched explanation interaction events",
    )


class EventBatchResponse(BaseModel):
    accepted: int
    duplicates: int


class AdminMetricsResponse(BaseModel):
    total_users: int
    arm_distribution: dict[str, int]
    total_attempts: int
    total_explanations: int
    p50_latency_ms: float
    p95_latency_ms: float
