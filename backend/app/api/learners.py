"""Learner state, audit history and "why we think this" routes (Open Learner Model).

Owner: Mit.
"""

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import ExplainabilityDep, LearnerModelDep
from app.api.errors import not_found
from app.api.schemas import StateUpdateView
from app.auth import DbDep, LearnerDep
from app.contracts.learner import LearnerState, StateDelta
from app.contracts.xai import BeliefExplanation
from app.db import models as m

router = APIRouter(prefix="/learners", tags=["learners"])


@router.get("/me/state", response_model=LearnerState, summary="Your learner state (dashboard)")
def get_learner_state(current: LearnerDep, learner_model: LearnerModelDep) -> LearnerState:
    return learner_model.get_state(current.id)


@router.get(
    "/me/history",
    response_model=list[StateUpdateView],
    summary="Your state updates, newest first ('Why we think this')",
)
def get_learner_history(
    current: LearnerDep,
    session: DbDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_id: Annotated[int | None, Query(ge=1, description="updates older than this id")] = None,
) -> list[StateUpdateView]:
    query = select(m.StateUpdateRow).where(m.StateUpdateRow.user_id == current.id)
    if before_id is not None:
        query = query.where(m.StateUpdateRow.id < before_id)
    rows = session.scalars(query.order_by(m.StateUpdateRow.id.desc()).limit(limit))
    return [
        StateUpdateView(
            id=r.id,
            user_id=r.user_id,
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
    summary="Why the system believes something about you (XAI E4)",
)
def explain_belief(
    current: LearnerDep,
    explainability: ExplainabilityDep,
    subject: Annotated[str, Query(min_length=1, max_length=100, description="concept or trait")],
) -> BeliefExplanation:
    try:
        return explainability.explain_belief(current.id, subject)
    except LookupError:
        raise not_found("subject") from None
