"""POST /attempts: grade an answer and update the learner model.

Owner: Mit. Only items this learner was actually served can be answered, each once:
- a practice item through its `recommendation_id`,
- a micro-check through its `explanation_id` (this also closes the explanation's feedback loop:
  apply_attempt first, then summarize -> apply_explanation_feedback, tasks/ronit.md),
- a pre/post-test item (`pretest-*` / `posttest-*`) once per learner, without updating the model.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import Services, Svc
from app.api.errors import conflict, invalid, not_found
from app.api.schemas import AttemptResultOut
from app.auth import ConsentedUser
from app.contracts.graph import Item
from app.contracts.learner import AttemptIn, AttemptRecord, StateDelta
from app.db import models as m
from app.graph.service import is_test_item

router = APIRouter(prefix="/attempts", tags=["attempts"])

MAX_RESPONSE_CHARS = 500
MAX_LATENCY_MS = 60 * 60 * 1000  # longer waits are clamped: the learner walked away
MAX_HINTS = 20


def normalise(text: str) -> str:
    return " ".join(text.split()).casefold()


def grade(item: Item, response: str) -> bool:
    if item.kind == "mcq":
        if response not in item.options:
            raise invalid("INVALID_OPTION", "The answer must be one of the item's options")
        return response == item.answer
    return normalise(response) == normalise(item.answer)


def _served(svc: Services, user_id: uuid.UUID, payload: AttemptIn, item: Item) -> None:
    """Raise unless this learner was served this item and has not answered it yet. The served
    row is locked, so two concurrent submissions of the same answer cannot both pass."""
    if payload.recommendation_id is not None and payload.explanation_id is not None:
        raise invalid("AMBIGUOUS_ATTEMPT", "Send recommendation_id or explanation_id, not both")
    if payload.recommendation_id is not None:
        rec = svc.session.scalar(
            select(m.RecommendationRow)
            .where(m.RecommendationRow.id == payload.recommendation_id)
            .with_for_update()
        )
        if rec is None or rec.user_id != user_id:
            raise not_found("Recommendation")
        if rec.item_id != item.id:
            raise invalid("ITEM_MISMATCH", "This item was not served for that recommendation")
        done = select(m.AttemptRow.id).where(m.AttemptRow.recommendation_id == rec.id)
    elif payload.explanation_id is not None:
        exp = svc.session.scalar(
            select(m.ExplanationRow)
            .where(m.ExplanationRow.id == payload.explanation_id)
            .with_for_update()
        )
        if exp is None or exp.user_id != user_id:
            raise not_found("Explanation")
        if exp.followup_item_id != item.id:
            raise invalid("ITEM_MISMATCH", "This item is not that explanation's micro-check")
        done = select(m.AttemptRow.id).where(
            m.AttemptRow.explanation_id == exp.id, m.AttemptRow.item_id == item.id
        )
    elif is_test_item(item.id):
        svc.session.execute(  # serialise this learner's test submissions
            select(m.User.id).where(m.User.id == user_id).with_for_update()
        )
        done = select(m.AttemptRow.id).where(
            m.AttemptRow.user_id == user_id, m.AttemptRow.item_id == item.id
        )
    else:
        raise invalid("ITEM_NOT_SERVED", "Answer items from your session (send recommendation_id)")
    if svc.session.scalar(done.limit(1)) is not None:
        raise conflict("ALREADY_ANSWERED", "This item has already been answered")


@router.post("", response_model=AttemptResultOut, summary="Submit an answer")
def record_attempt(payload: AttemptIn, user: ConsentedUser, svc: Svc) -> AttemptResultOut:
    if len(payload.response) > MAX_RESPONSE_CHARS or not payload.response.strip():
        raise invalid("INVALID_RESPONSE", f"Answers must be 1 to {MAX_RESPONSE_CHARS} characters")
    if not 0 <= payload.hints_used <= MAX_HINTS:
        raise invalid("INVALID_HINTS", f"hints_used must be between 0 and {MAX_HINTS}")
    try:
        item = svc.graph.get_item(payload.item_id)
    except LookupError:
        raise not_found("Item") from None
    _served(svc, user.id, payload, item)

    correct = grade(item, payload.response)
    record = AttemptRecord(
        **payload.model_dump(exclude={"latency_ms"}),
        latency_ms=min(payload.latency_ms, MAX_LATENCY_MS),
        id=uuid.uuid4(),
        user_id=user.id,
        concept_id=item.concept_id,
        correct=correct,
        created_at=datetime.now(UTC),
    )
    if is_test_item(item.id):  # tests measure learning; they never move the model
        svc.learner_model.record_test_attempt(record)
        svc.session.commit()
        return AttemptResultOut(
            correct=correct,
            correct_answer=None,  # never reveal pre/post-test answers
            delta=StateDelta(user_id=user.id, source="attempt", source_id=str(record.id)),
        )

    delta = svc.learner_model.apply_attempt(record)
    result = AttemptResultOut(
        correct=correct,
        correct_answer=item.answer,
        delta=delta,
        change=svc.xai.explain_change(delta),
    )
    if payload.explanation_id is not None:
        summary = svc.analyzer.summarize(payload.explanation_id)
        svc.analyzer.store_summary(summary)
        feedback = svc.learner_model.apply_explanation_feedback(summary)
        result.feedback_change = svc.xai.explain_change(feedback)
    svc.session.commit()
    return result
