"""Explanation retrieval and interaction telemetry routes.

Owner: Mit.
"""

from uuid import UUID

from fastapi import APIRouter

from app.api.attempts import close_feedback_loop
from app.api.deps import ExplainabilityDep, FeedbackAnalyzerDep, LearnerModelDep
from app.api.errors import not_found
from app.api.schemas import EventBatchIn, EventBatchResponse, FeedbackOut
from app.auth import CurrentUser, DbDep, LearnerDep
from app.contracts.explanation import Explanation, ExplanationEventIn
from app.db import models as m
from app.telemetry import explanation_from_row

router = APIRouter(prefix="/explanations", tags=["explanations"])


def own_explanation(session, current: CurrentUser, explanation_id: UUID) -> m.ExplanationRow:
    row = session.get(m.ExplanationRow, explanation_id)
    if row is None or row.user_id != current.id:
        raise not_found("explanation")
    return row


@router.get(
    "/{explanation_id}", response_model=Explanation, summary="Fetch one of your explanations"
)
def get_explanation(explanation_id: UUID, current: LearnerDep, session: DbDep) -> Explanation:
    return explanation_from_row(own_explanation(session, current, explanation_id))


@router.post(
    "/{explanation_id}/events",
    response_model=EventBatchResponse,
    summary="Record batched interaction events for an explanation",
)
def record_events(
    explanation_id: UUID,
    payload: EventBatchIn,
    current: LearnerDep,
    session: DbDep,
    analyzer: FeedbackAnalyzerDep,
) -> EventBatchResponse:
    own_explanation(session, current, explanation_id)
    events = [ExplanationEventIn.model_validate(e.model_dump()) for e in payload.events]
    accepted, duplicates = analyzer.record_events(explanation_id, current.id, events)
    session.commit()
    return EventBatchResponse(accepted=accepted, duplicates=duplicates)


@router.post(
    "/{explanation_id}/close",
    response_model=FeedbackOut,
    summary="Finalise an explanation dismissed without answering its micro-check",
)
def close_explanation(
    explanation_id: UUID,
    current: LearnerDep,
    session: DbDep,
    analyzer: FeedbackAnalyzerDep,
    learner_model: LearnerModelDep,
    explainability: ExplainabilityDep,
) -> FeedbackOut:
    row = own_explanation(session, current, explanation_id)
    stored = session.get(m.ExplanationFeedbackRow, explanation_id)
    if stored is not None:  # already summarised (answered or closed before): nothing new to apply
        return FeedbackOut.model_validate(stored.summary)
    delta = close_feedback_loop(session, analyzer, learner_model, row, followup_correct=None)
    summary = session.get(m.ExplanationFeedbackRow, explanation_id).summary
    session.commit()
    return FeedbackOut(**summary, change=explainability.explain_change(delta))
