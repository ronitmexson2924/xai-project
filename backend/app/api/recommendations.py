"""'Why this?' for a recommendation (XAI E1-E3, docs/XAI_DESIGN.md).

Owner: Mit.
"""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import ExplainabilityDep
from app.api.errors import not_found
from app.auth import DbDep, LearnerDep
from app.contracts.xai import RecommendationWhy
from app.db import models as m

router = APIRouter(prefix="/recommendations", tags=["xai"])


@router.get(
    "/{recommendation_id}/why",
    response_model=RecommendationWhy,
    summary="Why this question, what would change it, and why the explanation looks this way",
)
def why(
    recommendation_id: UUID, current: LearnerDep, session: DbDep, explainability: ExplainabilityDep
) -> RecommendationWhy:
    row = session.get(m.RecommendationRow, recommendation_id)
    if row is None or row.user_id != current.id:
        raise not_found("recommendation")
    try:
        return explainability.why(recommendation_id)
    except LookupError:
        raise not_found("recommendation") from None
