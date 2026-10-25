"""Learner state and audit history routes (Open Learner Model).

Owner: Mit.
"""

from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import LearnerModelDep
from app.api.schemas import StateUpdateView
from app.auth import UserResponse, require_consent
from app.contracts.learner import LearnerState, StateDelta

router = APIRouter(prefix="/learners", tags=["learners"])

# In-memory history log for development/fakes until R0 database audit table is active
_audit_history: dict[UUID, list[StateUpdateView]] = defaultdict(list)
_audit_counter = 0


def log_state_update(user_id: UUID, delta: StateDelta) -> None:
    global _audit_counter
    _audit_counter += 1
    view = StateUpdateView(
        id=_audit_counter,
        user_id=user_id,
        source=delta.source,
        source_id=delta.source_id,
        delta=delta,
        created_at=datetime.now(UTC),
    )
    _audit_history[user_id].append(view)


def clear_audit_history() -> None:
    global _audit_counter
    _audit_counter = 0
    _audit_history.clear()


@router.get(
    "/me/state",
    response_model=LearnerState,
    summary="Get unified learner state for open learner model dashboard",
)
def get_learner_state(
    current_user: Annotated[UserResponse, Depends(require_consent)],
    learner_model: LearnerModelDep,
) -> LearnerState:
    return learner_model.get_state(current_user.id)


@router.get(
    "/me/history",
    response_model=list[StateUpdateView],
    summary="Get chronological state update history ('Why we think this')",
)
def get_learner_history(
    current_user: Annotated[UserResponse, Depends(require_consent)],
) -> list[StateUpdateView]:
    return _audit_history.get(current_user.id, [])
