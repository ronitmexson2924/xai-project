"""Session management and recommendation routes.

Owner: Mit.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import (
    ExplainerDep,
    FeedbackAnalyzerDep,
    GraphDep,
    LearnerModelDep,
    PlannerDep,
)
from app.api.flags import get_arm_features
from app.auth import UserResponse, require_consent
from app.contracts.explanation import ExplanationRequest, StyleParams
from app.contracts.graph import PublicItem
from app.contracts.planning import NextStepResponse

router = APIRouter(prefix="/session", tags=["session"])


@router.post(
    "/next",
    response_model=NextStepResponse,
    summary="Get the next learning recommendation, explanation, and micro-check",
)
def next_step(
    current_user: Annotated[UserResponse, Depends(require_consent)],
    learner_model: LearnerModelDep,
    planner: PlannerDep,
    explainer: ExplainerDep,
    analyzer: FeedbackAnalyzerDep,
    graph: GraphDep,
) -> NextStepResponse:
    # 1. Fetch current learner state
    state = learner_model.get_state(current_user.id)

    # 2. Re-planner decides next concept recommendation and reason evidence
    rec = planner.next_step(state)

    # 3. Choose presentation style governed by study arm feature flags
    features = get_arm_features(current_user.arm)
    if features.forced_style is not None:
        style = features.forced_style
        style_source = "generic"
    else:
        style, style_source = planner.choose_style(state, rec.target_concept_id)
        if features.allow_trait_personalization and style_source == "generic":
            traits = state.traits.traits
            abs_pref = (
                traits["abstraction_preference"].mean if "abstraction_preference" in traits else 0.5
            )
            depth_pref = traits["depth_preference"].mean if "depth_preference" in traits else 0.5
            style = StyleParams(
                example_first=abs_pref < 0.5,
                length="medium",
                depth="why" if depth_pref > 0.6 else "how",
            )
            style_source = "trait_mapped"
        elif not features.allow_exploration and style_source in ("thompson", "exploration"):
            style_source = "trait_mapped"

    # 4. Explainer generates or retrieves grounded explanation
    req = ExplanationRequest(
        user_id=current_user.id,
        recommendation_id=rec.id,
        concept_ids=[rec.target_concept_id],
        reasons=rec.reasons,
        style=style,
        style_source=style_source,
        followup_item_id=rec.item_id,
    )
    explanation = explainer.explain(req)

    # Register explanation with feedback analyzer for telemetry capture
    if hasattr(analyzer, "register"):
        analyzer.register(explanation)

    # 5. Fetch associated item (if any), strictly stripping out the answer
    public_item: PublicItem | None = None
    if rec.item_id:
        raw_item = graph.get_item(rec.item_id)
        public_item = PublicItem(
            id=raw_item.id,
            concept_id=raw_item.concept_id,
            kind=raw_item.kind,
            stem=raw_item.stem,
            options=raw_item.options,
        )

    return NextStepResponse(
        recommendation=rec,
        explanation=explanation,
        item=public_item,
    )
