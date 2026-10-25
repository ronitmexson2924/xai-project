"""Onboarding: the psychometric questionnaire (content/questionnaire.yaml, MODEL_SPEC §2.1).

Owner: Mit.
"""

from fastapi import APIRouter

from app.api.deps import Svc
from app.api.errors import invalid
from app.api.schemas import QuestionnaireAnswersIn, QuestionnaireItemOut
from app.auth import ConsentedUser
from app.contracts.learner import StateDelta

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get(
    "/questionnaire",
    response_model=list[QuestionnaireItemOut],
    summary="Get the questionnaire items (id and text only)",
)
def get_questionnaire(_: ConsentedUser, svc: Svc) -> list[QuestionnaireItemOut]:
    items = sorted(svc.learner_model.questionnaire_items(), key=lambda i: i.id)
    return [QuestionnaireItemOut(id=i.id, text=i.text) for i in items]


@router.post(
    "/questionnaire",
    response_model=StateDelta,
    summary="Submit questionnaire answers (once) to initialise the learner's traits",
)
def submit_questionnaire(
    payload: QuestionnaireAnswersIn, user: ConsentedUser, svc: Svc
) -> StateDelta:
    expected = {i.id for i in svc.learner_model.questionnaire_items()}
    if missing := sorted(expected - set(payload.answers)):
        raise invalid("INCOMPLETE_QUESTIONNAIRE", f"Please answer every item ({len(missing)} left)")
    try:
        delta = svc.learner_model.init_from_questionnaire(user.id, payload.answers)
    except ValueError as err:  # unknown item ids or ratings outside 1..5
        raise invalid("INVALID_ANSWERS", str(err)) from err
    svc.session.commit()
    return delta
