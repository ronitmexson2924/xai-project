"""The performance model (a trained neural network) and its explanations: SHAP, LIME, LRP and
DiCE counterfactuals (docs/XAI_DESIGN.md section 7).

Owner: Ronit (model), Mit (API).
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import GraphDep
from app.api.errors import not_found
from app.auth import DbDep, LearnerDep, UserDep
from app.ml.service import ModelInsight, insight_for_recommendation, model_card

router = APIRouter(tags=["xai"])


@router.get(
    "/recommendations/{recommendation_id}/model",
    response_model=ModelInsight,
    summary="The model's predicted chance of a correct answer, explained with SHAP, LIME, LRP "
    "and DiCE counterfactuals",
)
def recommendation_model(
    recommendation_id: UUID, current: LearnerDep, session: DbDep, graph: GraphDep
) -> ModelInsight:
    try:
        return insight_for_recommendation(session, graph, current.id, recommendation_id)
    except LookupError:
        raise not_found("recommendation") from None


@router.get(
    "/model/card",
    summary="How the performance model was trained, how well it predicts compared with BKT, and "
    "what drives it overall",
)
def card(current: UserDep) -> dict[str, Any]:
    return model_card()
