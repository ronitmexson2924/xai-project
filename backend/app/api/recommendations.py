"""GET /recommendations/{id}/why: the "Why this?" panel (XAI E1-E3, docs/XAI_DESIGN.md).

Owner: Mit. Returns the rationale stored when the planner decided; it is never recomputed.
"""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import Svc
from app.api.errors import not_found
from app.auth import ConsentedUser
from app.contracts.xai import RecommendationWhy
from app.db import models as m

router = APIRouter(prefix="/recommendations", tags=["xai"])


@router.get("/{recommendation_id}/why", response_model=RecommendationWhy, summary="Why this?")
def why(recommendation_id: UUID, user: ConsentedUser, svc: Svc) -> RecommendationWhy:
    row = svc.session.get(m.RecommendationRow, recommendation_id)
    if row is None or row.user_id != user.id:
        raise not_found("Recommendation")
    try:
        return svc.xai.why(recommendation_id)
    except LookupError:
        raise not_found("Rationale") from None
