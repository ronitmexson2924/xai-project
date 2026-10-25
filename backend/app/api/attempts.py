"""Learner attempts and grading routes.

Owner: Mit.
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.deps import FeedbackAnalyzerDep, GraphDep, LearnerModelDep
from app.api.learners import log_state_update
from app.auth import UserResponse, require_consent
from app.auth.store import (
    DEMO_ADVANCED_ID,
    DEMO_INTERMEDIATE_ID,
    DEMO_NOVICE_ID,
)
from app.contracts.explanation import ExplanationEventIn
from app.contracts.learner import AttemptIn, AttemptRecord, AttemptResult
from app.contracts.services import FeedbackAnalyzer, LearnerModelService

router = APIRouter(prefix="/attempts", tags=["attempts"])

# In-memory attempt log for research audit and CSV export
_attempts_log: list[AttemptRecord] = []


def seed_demo_attempts() -> None:
    now = datetime.now(UTC)
    demos = [
        AttemptRecord(
            id=uuid4(),
            user_id=DEMO_NOVICE_ID,
            item_id="loops-1",
            concept_id="loops",
            response="3",
            correct=True,
            latency_ms=12400,
            hints_used=0,
            confidence=4,
            created_at=now,
        ),
        AttemptRecord(
            id=uuid4(),
            user_id=DEMO_NOVICE_ID,
            item_id="recursion-base-case-1",
            concept_id="recursion-base-case",
            response="0",
            correct=False,
            latency_ms=24500,
            hints_used=1,
            confidence=2,
            created_at=now,
        ),
        AttemptRecord(
            id=uuid4(),
            user_id=DEMO_INTERMEDIATE_ID,
            item_id="array-indexing-1",
            concept_id="array-indexing",
            response="arr[i]",
            correct=True,
            latency_ms=8400,
            hints_used=0,
            confidence=5,
            created_at=now,
        ),
        AttemptRecord(
            id=uuid4(),
            user_id=DEMO_ADVANCED_ID,
            item_id="topological-sort-1",
            concept_id="topological-sort",
            response="Kahn algorithm with queue",
            correct=True,
            latency_ms=6200,
            hints_used=0,
            confidence=5,
            created_at=now,
        ),
    ]
    _attempts_log.extend(demos)


seed_demo_attempts()


def get_attempts_log() -> list[AttemptRecord]:
    return list(_attempts_log)


def record_attempt_to_log(rec: AttemptRecord) -> None:
    _attempts_log.append(rec)


def clear_attempts_log(seed_demos: bool = True) -> None:
    _attempts_log.clear()
    if seed_demos:
        seed_demo_attempts()


def _process_explanation_feedback(
    analyzer: FeedbackAnalyzer,
    learner_model: LearnerModelService,
    explanation_id: UUID,
    user_id: UUID,
    item_id: str,
    correct: bool,
) -> None:
    """Background task closing the feedback loop upon micro-check submission."""
    event = ExplanationEventIn(
        idempotency_key=uuid4(),
        type="followup_answered",
        client_ts=datetime.now(UTC),
        payload={"item_id": item_id, "correct": correct},
    )
    analyzer.record_events(explanation_id, user_id, [event])
    summary = analyzer.summarize(explanation_id)
    feedback_delta = learner_model.apply_explanation_feedback(summary)
    log_state_update(user_id, feedback_delta)


@router.post(
    "",
    response_model=AttemptResult,
    summary="Submit an answer to a question or micro-check",
)
def record_attempt(
    payload: AttemptIn,
    background_tasks: BackgroundTasks,
    current_user: Annotated[UserResponse, Depends(require_consent)],
    graph: GraphDep,
    learner_model: LearnerModelDep,
    analyzer: FeedbackAnalyzerDep,
) -> AttemptResult:
    try:
        item = graph.get_item(payload.item_id)
    except StopIteration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "ITEM_NOT_FOUND",
                    "message": f"Item {payload.item_id} does not exist",
                }
            },
        ) from None

    correct = payload.response.strip().lower() == item.answer.strip().lower()
    attempt_id = uuid4()

    record = AttemptRecord(
        id=attempt_id,
        user_id=current_user.id,
        concept_id=item.concept_id,
        correct=correct,
        created_at=datetime.now(UTC),
        item_id=payload.item_id,
        response=payload.response,
        latency_ms=payload.latency_ms,
        hints_used=payload.hints_used,
        confidence=payload.confidence,
        recommendation_id=payload.recommendation_id,
        explanation_id=payload.explanation_id,
    )
    record_attempt_to_log(record)

    # 1. Update concept mastery (synchronous O(1) BKT update)
    delta = learner_model.apply_attempt(record)
    log_state_update(current_user.id, delta)

    # 2. If this item was a micro-check for an explanation, close the feedback loop asynchronously
    if payload.explanation_id is not None:
        background_tasks.add_task(
            _process_explanation_feedback,
            analyzer=analyzer,
            learner_model=learner_model,
            explanation_id=payload.explanation_id,
            user_id=current_user.id,
            item_id=payload.item_id,
            correct=correct,
        )

    return AttemptResult(
        correct=correct,
        correct_answer=item.answer,
        delta=delta,
    )
