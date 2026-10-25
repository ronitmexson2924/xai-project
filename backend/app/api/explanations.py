"""Explanations: fetch, interaction telemetry, and closing the feedback loop.

Owner: Mit. Every route checks that the explanation belongs to the caller; someone else's id
gets the same 404 as an id that does not exist.
"""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import Services, Svc
from app.api.errors import not_found
from app.api.schemas import EventBatchIn, EventBatchResponse
from app.api.session import explanation_out
from app.auth import ConsentedUser
from app.contracts.explanation import Explanation, ExplanationFeedbackSummary
from app.db import models as m

router = APIRouter(prefix="/explanations", tags=["explanations"])


def own_explanation(svc: Services, explanation_id: UUID, user_id: UUID, lock: bool = False):  # noqa: ANN201
    query = select(m.ExplanationRow).where(m.ExplanationRow.id == explanation_id)
    row = svc.session.scalar(query.with_for_update() if lock else query)
    if row is None or row.user_id != user_id:
        raise not_found("Explanation")
    return row


@router.get("/{explanation_id}", response_model=Explanation, summary="Fetch an explanation")
def get_explanation(explanation_id: UUID, user: ConsentedUser, svc: Svc) -> Explanation:
    return explanation_out(own_explanation(svc, explanation_id, user.id))


@router.post(
    "/{explanation_id}/events",
    response_model=EventBatchResponse,
    summary="Record interaction events for an explanation (idempotent per idempotency_key)",
)
def record_events(
    explanation_id: UUID, payload: EventBatchIn, user: ConsentedUser, svc: Svc
) -> EventBatchResponse:
    own_explanation(svc, explanation_id, user.id)
    accepted, duplicates = svc.analyzer.record_events(explanation_id, user.id, payload.events)
    svc.session.commit()
    return EventBatchResponse(accepted=accepted, duplicates=duplicates)


@router.post(
    "/{explanation_id}/close",
    response_model=ExplanationFeedbackSummary,
    summary="Finish an explanation that had no micro-check answer, applying its feedback",
)
def close_explanation(
    explanation_id: UUID, user: ConsentedUser, svc: Svc
) -> ExplanationFeedbackSummary:
    own_explanation(svc, explanation_id, user.id, lock=True)
    stored = svc.session.get(m.ExplanationFeedbackRow, explanation_id)
    if stored is not None and stored.applied_at is not None:  # closing twice changes nothing
        return ExplanationFeedbackSummary.model_validate(stored.summary)
    summary = svc.analyzer.summarize(explanation_id)
    svc.analyzer.store_summary(summary)
    svc.learner_model.apply_explanation_feedback(summary)
    svc.session.commit()
    return summary
