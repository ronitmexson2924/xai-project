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
from app.auth.store import DEMO_ADVANCED_ID, DEMO_INTERMEDIATE_ID, DEMO_NOVICE_ID
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


def seed_demo_audit_history() -> None:
    # Novice audit updates
    log_state_update(
        DEMO_NOVICE_ID,
        StateDelta(
            user_id=DEMO_NOVICE_ID,
            source="questionnaire",
            source_id="onboarding-survey",
            notes=["Calibrated baseline traits from intake questionnaire"],
        ),
    )
    log_state_update(
        DEMO_NOVICE_ID,
        StateDelta(
            user_id=DEMO_NOVICE_ID,
            source="attempt",
            source_id="att-nov-01",
            mastery_changes={"loops": (0.50, 0.65)},
            notes=["Answered loops-1 correctly (+0.15 mastery)"],
        ),
    )
    log_state_update(
        DEMO_NOVICE_ID,
        StateDelta(
            user_id=DEMO_NOVICE_ID,
            source="attempt",
            source_id="att-nov-02",
            mastery_changes={"recursion-base-case": (0.32, 0.22)},
            notes=["Distractor chosen maps to misconception: recursion-never-halts"],
        ),
    )
    log_state_update(
        DEMO_NOVICE_ID,
        StateDelta(
            user_id=DEMO_NOVICE_ID,
            source="explanation_feedback",
            source_id="exp-nov-01",
            trait_changes={"abstraction_preference": (0.20, 0.18)},
            notes=["Clarity rating 4/5: nudged preference toward concrete examples"],
        ),
    )

    # Intermediate audit updates
    log_state_update(
        DEMO_INTERMEDIATE_ID,
        StateDelta(
            user_id=DEMO_INTERMEDIATE_ID,
            source="questionnaire",
            source_id="onboarding-survey",
            notes=["Calibrated balanced traits: moderate abstraction, strong load tolerance"],
        ),
    )
    log_state_update(
        DEMO_INTERMEDIATE_ID,
        StateDelta(
            user_id=DEMO_INTERMEDIATE_ID,
            source="attempt",
            source_id="att-int-01",
            mastery_changes={"array-indexing": (0.75, 0.88)},
            notes=["Array indexing pattern applied with high accuracy"],
        ),
    )
    log_state_update(
        DEMO_INTERMEDIATE_ID,
        StateDelta(
            user_id=DEMO_INTERMEDIATE_ID,
            source="attempt",
            source_id="att-int-02",
            mastery_changes={"two-pointers-technique": (0.70, 0.82)},
            notes=["Solved two-pointers question within 8400ms"],
        ),
    )
    log_state_update(
        DEMO_INTERMEDIATE_ID,
        StateDelta(
            user_id=DEMO_INTERMEDIATE_ID,
            source="explanation_feedback",
            source_id="exp-int-01",
            trait_changes={"depth_preference": (0.70, 0.72)},
            notes=["Rated tree recursion explanation 5/5: increased depth preference"],
        ),
    )

    # Advanced audit updates
    log_state_update(
        DEMO_ADVANCED_ID,
        StateDelta(
            user_id=DEMO_ADVANCED_ID,
            source="questionnaire",
            source_id="onboarding-survey",
            notes=["Calibrated senior baseline: rule-first, high depth and endurance"],
        ),
    )
    log_state_update(
        DEMO_ADVANCED_ID,
        StateDelta(
            user_id=DEMO_ADVANCED_ID,
            source="attempt",
            source_id="att-adv-01",
            mastery_changes={"topological-sort": (0.80, 0.92)},
            notes=["Mastered topological sort with Kahn's algorithm"],
        ),
    )
    log_state_update(
        DEMO_ADVANCED_ID,
        StateDelta(
            user_id=DEMO_ADVANCED_ID,
            source="attempt",
            source_id="att-adv-02",
            mastery_changes={"dp-state-transition-2d": (0.78, 0.88)},
            notes=["Formulated 2D DP recurrence without hints"],
        ),
    )


# Seed upon module load
seed_demo_audit_history()


def clear_audit_history(seed_demos: bool = True) -> None:
    global _audit_counter
    _audit_counter = 0
    _audit_history.clear()
    if seed_demos:
        seed_demo_audit_history()


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
