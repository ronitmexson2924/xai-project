"""Onboarding and intake questionnaire routes.

Owner: Mit.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import LearnerModelDep
from app.api.learners import log_state_update
from app.api.schemas import QuestionnaireAnswersIn, QuestionnaireItem
from app.auth import UserResponse, require_consent
from app.contracts.learner import StateDelta

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# Curated intake questions representing the 5 psychometric traits
# (From psychometrics specification, D4 in PROJECT_BRIEF)
DEFAULT_QUESTIONNAIRE_ITEMS = [
    QuestionnaireItem(
        id="abs-1",
        trait="abstraction_preference",
        text=(
            "I understand algorithm concepts much faster when given a concrete code example first."
        ),
        reverse_scored=True,
        source="Felder-Silverman Index of Learning Styles (adapted)",
    ),
    QuestionnaireItem(
        id="abs-2",
        trait="abstraction_preference",
        text=(
            "I prefer starting with formal mathematical definitions and invariant rules before"
            " examples."
        ),
        reverse_scored=False,
        source="Felder-Silverman Index of Learning Styles (adapted)",
    ),
    QuestionnaireItem(
        id="load-1",
        trait="load_tolerance",
        text="Dense, multi-paragraph technical explanations feel overwhelming to me.",
        reverse_scored=True,
        source="NASA-TLX Mental Demand Scale (adapted)",
    ),
    QuestionnaireItem(
        id="load-2",
        trait="load_tolerance",
        text=(
            "I easily digest long, detailed walkthroughs without needing concepts chunked into"
            " small parts."
        ),
        reverse_scored=False,
        source="Cognitive Load Scale (adapted)",
    ),
    QuestionnaireItem(
        id="depth-1",
        trait="depth_preference",
        text=(
            "I care most about how to implement an algorithm step-by-step rather than theoretical"
            " justification."
        ),
        reverse_scored=True,
        source="Deep vs Surface Approach to Learning Scale",
    ),
    QuestionnaireItem(
        id="depth-2",
        trait="depth_preference",
        text=(
            "I need to know the mathematical reason why an algorithm works before I feel confident"
            " using it."
        ),
        reverse_scored=False,
        source="Deep vs Surface Approach to Learning Scale",
    ),
    QuestionnaireItem(
        id="pers-1",
        trait="persistence",
        text=(
            "When stuck on a tricky recursive algorithm, I keep trying different strategies"
            " without giving up quickly."
        ),
        reverse_scored=False,
        source="Short Grit Scale (Grit-S)",
    ),
    QuestionnaireItem(
        id="eff-1",
        trait="self_efficacy",
        text=(
            "I feel confident in my ability to learn and master advanced Data Structures and"
            " Algorithms."
        ),
        reverse_scored=False,
        source="General Self-Efficacy Scale (GSES)",
    ),
]


@router.get(
    "/questionnaire",
    response_model=list[QuestionnaireItem],
    summary="Get psychometric intake questionnaire items",
)
def get_questionnaire(
    _: Annotated[UserResponse, Depends(require_consent)],
) -> list[QuestionnaireItem]:
    return DEFAULT_QUESTIONNAIRE_ITEMS


@router.post(
    "/questionnaire",
    response_model=StateDelta,
    summary="Submit intake questionnaire answers to initialize trait state",
)
def submit_questionnaire(
    payload: QuestionnaireAnswersIn,
    current_user: Annotated[UserResponse, Depends(require_consent)],
    learner_model: LearnerModelDep,
) -> StateDelta:
    for item_id, rating in payload.answers.items():
        if rating < 1 or rating > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_RATING",
                        "message": f"Rating for {item_id} must be between 1 and 5 (got {rating})",
                    }
                },
            )

    delta = learner_model.init_from_questionnaire(current_user.id, payload.answers)
    log_state_update(current_user.id, delta)
    return delta
