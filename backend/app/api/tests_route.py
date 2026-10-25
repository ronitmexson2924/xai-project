"""Pre/post learning-gain tests (EVALUATION_PLAN H4).

Owner: Mit.
Each test is taken once. Answers are graded and stored with LearnerModel.record_test_attempt, which
never touches the learner model, and neither the score nor the right answers are shown: the two
tests are parallel forms, so revealing answers would contaminate the post-test.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.api.attempts import grade
from app.api.deps import GraphDep, LearnerModelDep
from app.api.errors import UNPROCESSABLE, api_error
from app.api.schemas import TestAnswersIn, TestOut, TestPhase, TestSubmitted
from app.api.session import public_item
from app.auth import DbDep, LearnerDep
from app.contracts.learner import AttemptRecord
from app.db import models as m
from app.graph.service import GraphSnapshot

router = APIRouter(prefix="/tests", tags=["tests"])


def phase_items(graph: GraphSnapshot, phase: TestPhase) -> list[str]:
    return [i for i in graph.test_item_ids if i.startswith(f"{phase}-")]


def answered(session, user_id: uuid.UUID, item_ids: list[str]) -> int:
    if not item_ids:
        return 0
    return session.scalar(
        select(func.count())
        .select_from(m.AttemptRow)
        .where(m.AttemptRow.user_id == user_id, m.AttemptRow.item_id.in_(item_ids))
    )


@router.get("/{phase}", response_model=TestOut, summary="The pre- or post-test questions")
def get_test(phase: TestPhase, current: LearnerDep, session: DbDep, graph: GraphDep) -> TestOut:
    ids = phase_items(graph, phase)
    return TestOut(
        phase=phase,
        items=[public_item(graph.get_item(i), current.id) for i in ids],
        submitted=answered(session, current.id, ids) > 0,
    )


@router.post(
    "/{phase}",
    response_model=TestSubmitted,
    status_code=status.HTTP_201_CREATED,
    summary="Submit the whole test once (unanswered questions count as wrong)",
)
def submit_test(
    phase: TestPhase,
    payload: TestAnswersIn,
    current: LearnerDep,
    session: DbDep,
    graph: GraphDep,
    learner_model: LearnerModelDep,
) -> TestSubmitted:
    ids = phase_items(graph, phase)
    if not ids:
        raise api_error(status.HTTP_404_NOT_FOUND, "TEST_NOT_FOUND", f"No {phase} is set up")
    if unknown := sorted(set(payload.answers) - set(ids)):
        raise api_error(
            UNPROCESSABLE,
            "UNKNOWN_TEST_ITEMS",
            f"{len(unknown)} answer(s) are not {phase} questions",
        )
    if phase == "posttest" and answered(session, current.id, phase_items(graph, "pretest")) == 0:
        raise api_error(
            status.HTTP_409_CONFLICT, "PRETEST_REQUIRED", "Take the pre-test before the post-test"
        )
    # one submission per test: lock the user row so two concurrent submissions serialise
    session.execute(select(m.User.id).where(m.User.id == current.id).with_for_update())
    if answered(session, current.id, ids) > 0:
        raise api_error(status.HTTP_409_CONFLICT, "ALREADY_SUBMITTED", f"The {phase} was taken")

    now = datetime.now(UTC)
    for item_id in ids:
        item = graph.get_item(item_id)
        response = payload.answers.get(item_id, "")
        learner_model.record_test_attempt(
            AttemptRecord(
                id=uuid.uuid4(),
                user_id=current.id,
                item_id=item_id,
                concept_id=item.concept_id,
                response=response,
                correct=bool(response) and grade(item, response),
                latency_ms=0,
                created_at=now,
            )
        )
    session.commit()
    return TestSubmitted(phase=phase, answered=sum(1 for i in ids if payload.answers.get(i)))
