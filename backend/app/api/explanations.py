"""Explanation retrieval and interaction telemetry routes.

Owner: Mit.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import FeedbackAnalyzerDep, LearnerModelDep
from app.api.learners import log_state_update
from app.api.schemas import EventBatchIn, EventBatchResponse
from app.auth import UserResponse, require_consent
from app.contracts.explanation import Explanation, ExplanationFeedbackSummary

router = APIRouter(prefix="/explanations", tags=["explanations"])


@router.get(
    "/{explanation_id}",
    response_model=Explanation,
    summary="Fetch explanation details by ID",
)
def get_explanation(
    explanation_id: UUID,
    _: Annotated[UserResponse, Depends(require_consent)],
    analyzer: FeedbackAnalyzerDep,
) -> Explanation:
    # Look up in registered explanations (or database in production)
    if hasattr(analyzer, "_explanations") and explanation_id in analyzer._explanations:
        return analyzer._explanations[explanation_id]

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": {
                "code": "EXPLANATION_NOT_FOUND",
                "message": f"Explanation {explanation_id} was not found",
            }
        },
    )


@router.post(
    "/{explanation_id}/events",
    response_model=EventBatchResponse,
    summary="Record batched interaction events for an explanation",
)
def record_events(
    explanation_id: UUID,
    payload: EventBatchIn,
    current_user: Annotated[UserResponse, Depends(require_consent)],
    analyzer: FeedbackAnalyzerDep,
) -> EventBatchResponse:
    accepted, duplicates = analyzer.record_events(
        explanation_id=explanation_id,
        user_id=current_user.id,
        events=payload.events,
    )
    return EventBatchResponse(accepted=accepted, duplicates=duplicates)


@router.post(
    "/{explanation_id}/close",
    response_model=ExplanationFeedbackSummary,
    summary="Finalize explanation interaction when dismissed without micro-check",
)
def close_explanation(
    explanation_id: UUID,
    current_user: Annotated[UserResponse, Depends(require_consent)],
    analyzer: FeedbackAnalyzerDep,
    learner_model: LearnerModelDep,
) -> ExplanationFeedbackSummary:
    try:
        summary = analyzer.summarize(explanation_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "EXPLANATION_NOT_FOUND",
                    "message": f"Explanation {explanation_id} does not exist",
                }
            },
        ) from None

    delta = learner_model.apply_explanation_feedback(summary)
    log_state_update(current_user.id, delta)
    return summary
