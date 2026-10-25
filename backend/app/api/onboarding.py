"""Onboarding and intake questionnaire routes.

Owner: Mit.
The questionnaire is content/questionnaire.yaml (seeded into the database, docs/MODEL_SPEC.md
§2.1); scoring and the trait priors live in the learner model.
"""

from fastapi import APIRouter, status

from app.api.deps import LearnerModelDep
from app.api.errors import api_error
from app.api.schemas import QuestionnaireAnswersIn, QuestionnaireItem
from app.auth import DbDep, LearnerDep
from app.contracts.learner import StateDelta

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get(
    "/questionnaire", response_model=list[QuestionnaireItem], summary="The intake questionnaire"
)
def get_questionnaire(_: LearnerDep, learner_model: LearnerModelDep) -> list[QuestionnaireItem]:
    return [
        QuestionnaireItem(
            id=i.id, trait=i.trait, text=i.text, reverse_scored=i.reverse_scored, source=i.source
        )
        for i in sorted(learner_model.questionnaire_items(), key=lambda i: i.id)
    ]


@router.post(
    "/questionnaire",
    response_model=StateDelta,
    summary="Submit the questionnaire once; it sets your starting trait estimates",
)
def submit_questionnaire(
    payload: QuestionnaireAnswersIn,
    current: LearnerDep,
    session: DbDep,
    learner_model: LearnerModelDep,
) -> StateDelta:
    known = {i.id for i in learner_model.questionnaire_items()}
    if missing := sorted(known - set(payload.answers)):
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "INCOMPLETE_QUESTIONNAIRE",
            f"{len(missing)} question(s) unanswered",
        )
    try:
        delta = learner_model.init_from_questionnaire(current.id, payload.answers)
    except ValueError as err:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_ANSWERS", str(err)) from None
    session.commit()
    return delta
