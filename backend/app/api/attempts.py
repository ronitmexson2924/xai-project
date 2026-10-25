"""Learner attempts and grading routes.

Owner: Mit.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import ExplainabilityDep, FeedbackAnalyzerDep, GraphDep, LearnerModelDep
from app.api.errors import api_error, not_found
from app.api.schemas import AttemptBody, AttemptResultOut
from app.auth import DbDep, LearnerDep
from app.contracts.explanation import ExplanationEventIn
from app.contracts.graph import Item
from app.contracts.learner import AttemptRecord, StateDelta
from app.db import models as m
from app.learner_model.service import LearnerModel
from app.telemetry import DbFeedbackAnalyzer

router = APIRouter(prefix="/attempts", tags=["attempts"])

FOLLOWUP_EVENT_NAMESPACE = uuid.UUID("6f1f6c1e-2b8f-4a59-9a39-9c7b4fd1c0de")


def normalise(text: str) -> str:
    return " ".join(text.split()).casefold()


def grade(item: Item, response: str) -> bool:
    """Server-side grading. Multiple choice must match the option exactly; free text ignores case
    and spacing."""
    if item.kind == "mcq":
        return response == item.answer
    return normalise(response) == normalise(item.answer)


def close_feedback_loop(
    session,
    analyzer: DbFeedbackAnalyzer,
    learner_model: LearnerModel,
    explanation: m.ExplanationRow,
    followup_correct: bool | None,
) -> StateDelta:
    """Summarise an explanation's interaction, store the summary and apply it to the learner
    model (Module C). Idempotent: a second call returns the delta of the first."""
    if followup_correct is not None:
        analyzer.record_events(
            explanation.id,
            explanation.user_id,
            [
                ExplanationEventIn(
                    # one server-written outcome per explanation: replays are deduplicated
                    idempotency_key=uuid.uuid5(FOLLOWUP_EVENT_NAMESPACE, str(explanation.id)),
                    type="followup_answered",
                    client_ts=datetime.now(UTC),
                    payload={"item_id": explanation.followup_item_id, "correct": followup_correct},
                )
            ],
        )
    summary = analyzer.summarize(explanation.id)
    if session.get(m.ExplanationFeedbackRow, explanation.id) is None:
        session.add(
            m.ExplanationFeedbackRow(
                explanation_id=explanation.id, summary=summary.model_dump(mode="json")
            )
        )
        session.flush()
    return learner_model.apply_explanation_feedback(summary)


@router.post(
    "",
    response_model=AttemptResultOut,
    summary="Submit the answer to the current recommendation's question",
)
def record_attempt(
    payload: AttemptBody,
    current: LearnerDep,
    session: DbDep,
    graph: GraphDep,
    learner_model: LearnerModelDep,
    analyzer: FeedbackAnalyzerDep,
    explainability: ExplainabilityDep,
) -> AttemptResultOut:
    rec = session.get(m.RecommendationRow, payload.recommendation_id)
    if rec is None or rec.user_id != current.id:
        raise not_found("recommendation")
    if rec.item_id != payload.item_id:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "ITEM_MISMATCH",
            "This answer is for a different question than the one recommended",
        )
    answered = session.scalar(
        select(m.AttemptRow.id).where(m.AttemptRow.recommendation_id == rec.id)
    )
    if answered is not None:
        raise api_error(
            status.HTTP_409_CONFLICT, "ALREADY_ANSWERED", "This question was already answered"
        )
    try:
        item = graph.get_item(payload.item_id)
    except KeyError:
        raise not_found("item") from None
    if item.kind == "mcq" and payload.response not in item.options:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "INVALID_OPTION",
            "The response must be one of the question's options",
        )

    explanation = session.scalar(
        select(m.ExplanationRow).where(m.ExplanationRow.recommendation_id == rec.id)
    )
    if payload.explanation_id is not None and (
        explanation is None or explanation.id != payload.explanation_id
    ):
        raise not_found("explanation")

    correct = grade(item, payload.response)
    record = AttemptRecord(
        id=uuid.uuid4(),
        user_id=current.id,
        concept_id=item.concept_id,
        correct=correct,
        created_at=datetime.now(UTC),
        item_id=payload.item_id,
        response=payload.response,
        latency_ms=payload.latency_ms,
        hints_used=payload.hints_used,
        confidence=payload.confidence,
        recommendation_id=rec.id,
        explanation_id=explanation.id if explanation is not None else None,
    )
    try:
        delta = learner_model.apply_attempt(record)
        notice = explainability.explain_change(delta)
        messages = list(notice.messages)
        if explanation is not None and explanation.followup_item_id == item.id:
            feedback = close_feedback_loop(session, analyzer, learner_model, explanation, correct)
            messages += explainability.explain_change(feedback).messages
        session.commit()
    except IntegrityError:  # a concurrent duplicate submission won the race
        session.rollback()
        raise api_error(
            status.HTTP_409_CONFLICT, "ALREADY_ANSWERED", "This question was already answered"
        ) from None

    change = notice.model_copy(update={"messages": messages})
    return AttemptResultOut(correct=correct, correct_answer=item.answer, delta=delta, change=change)
