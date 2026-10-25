"""Open learner model: state, history and "Why we think this" (XAI E4).

Owner: Mit.
"""

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import Svc
from app.api.errors import not_found
from app.api.schemas import StateUpdateView
from app.auth import ConsentedUser
from app.contracts.learner import LearnerState, StateDelta
from app.contracts.xai import BeliefExplanation
from app.db import models as m

router = APIRouter(prefix="/learners", tags=["learners"])


@router.get("/me/state", response_model=LearnerState, summary="The learner's current state")
def get_learner_state(user: ConsentedUser, svc: Svc) -> LearnerState:
    return svc.learner_model.get_state(user.id)


@router.get(
    "/me/history",
    response_model=list[StateUpdateView],
    summary="What changed the learner model, newest first",
)
def get_learner_history(
    user: ConsentedUser,
    svc: Svc,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[StateUpdateView]:
    rows = svc.session.scalars(
        select(m.StateUpdateRow)
        .where(m.StateUpdateRow.user_id == user.id)
        .order_by(m.StateUpdateRow.created_at.desc(), m.StateUpdateRow.id.desc())
        .limit(limit)
    )
    return [
        StateUpdateView(
            id=r.id,
            source=r.source,
            source_id=r.source_id,
            delta=StateDelta.model_validate(r.delta),
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/me/explain",
    response_model=BeliefExplanation,
    summary="Why the system believes what it does about a concept or trait (XAI E4)",
)
def explain_belief(
    user: ConsentedUser,
    svc: Svc,
    subject: Annotated[str, Query(min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$")],
) -> BeliefExplanation:
    try:
        return svc.xai.explain_belief(user.id, subject)
    except LookupError:
        raise not_found("Subject") from None
