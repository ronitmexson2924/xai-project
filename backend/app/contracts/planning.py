"""Module D outputs. Ronit produces; Mit's explainer and UI consume."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.contracts.explanation import Explanation
from app.contracts.graph import PublicItem
from app.contracts.reasons import ReasonEvidence

RecommendationKind = Literal["diagnostic_item", "practice_item", "remediate", "advance", "review"]


class Recommendation(BaseModel):
    id: UUID
    user_id: UUID
    kind: RecommendationKind
    target_concept_id: str
    item_id: str | None = None
    reasons: list[ReasonEvidence]
    policy_version: str


class NextStepResponse(BaseModel):
    """Response of POST /session/next."""

    recommendation: Recommendation
    explanation: Explanation
    item: PublicItem | None = None
