"""POST /session/next: the learning loop's next step (ARCHITECTURE.md sequence diagram).

Owner: Mit. get_state -> Planner.next_step -> choose_style (the planner applies the experiment
arm) -> explainer -> stored explanation. A step that was served but not answered yet is served
again, so reloading the page neither skips items nor floods the logs.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import Services, Svc
from app.api.errors import conflict
from app.auth import ConsentedUser
from app.contracts.explanation import Explanation, ExplanationRequest
from app.contracts.graph import Item, PublicItem
from app.contracts.planning import NextStepResponse, Recommendation
from app.contracts.reasons import ReasonEvidence
from app.db import models as m

router = APIRouter(prefix="/session", tags=["session"])

PENDING_FOR = timedelta(hours=2)  # an unanswered step older than this is replaced


def public(item: Item) -> PublicItem:
    return PublicItem(
        id=item.id, concept_id=item.concept_id, kind=item.kind, stem=item.stem, options=item.options
    )


def explanation_out(row: m.ExplanationRow) -> Explanation:
    return Explanation(
        id=row.id,
        recommendation_id=row.recommendation_id,
        user_id=row.user_id,
        concept_ids=list(row.concept_ids),
        style=row.style,
        style_source=row.style_source,
        body_markdown=row.body_markdown,
        source=row.source,
        prompt_version=row.prompt_version,
        model=row.model,
        followup_item_id=row.followup_item_id,
        latency_ms=row.latency_ms,
    )


def _pending(svc: Services, user_id) -> NextStepResponse | None:  # noqa: ANN001
    rec = svc.session.scalar(
        select(m.RecommendationRow)
        .where(m.RecommendationRow.user_id == user_id)
        .order_by(m.RecommendationRow.created_at.desc())
        .limit(1)
    )
    if rec is None or datetime.now(UTC) - rec.created_at > PENDING_FOR:
        return None
    answered = svc.session.scalar(
        select(m.AttemptRow.id).where(m.AttemptRow.recommendation_id == rec.id).limit(1)
    )
    explanation = svc.session.scalar(
        select(m.ExplanationRow).where(m.ExplanationRow.recommendation_id == rec.id)
    )
    if answered is not None or explanation is None or rec.item_id is None:
        return None
    try:
        item = svc.graph.get_item(rec.item_id)
    except LookupError:  # the item was withdrawn from review since
        return None
    return NextStepResponse(
        recommendation=Recommendation(
            id=rec.id,
            user_id=rec.user_id,
            kind=rec.kind,
            target_concept_id=rec.target_concept_id,
            item_id=rec.item_id,
            reasons=[ReasonEvidence.model_validate(r) for r in rec.reasons],
            policy_version=rec.policy_version,
        ),
        explanation=explanation_out(explanation),
        item=public(item),
    )


def _microcheck(svc: Services, user_id, concept_id: str) -> str | None:  # noqa: ANN001
    """The concept's micro-check this learner has answered least often (ties: by id)."""
    candidates = svc.graph.items_for_concept(concept_id, microcheck=True)
    if not candidates:
        return None
    seen = dict(
        svc.session.execute(
            select(m.AttemptRow.item_id, func.count())
            .where(
                m.AttemptRow.user_id == user_id,
                m.AttemptRow.item_id.in_([c.id for c in candidates]),
            )
            .group_by(m.AttemptRow.item_id)
        ).all()
    )
    return min(candidates, key=lambda c: (seen.get(c.id, 0), c.id)).id


@router.post(
    "/next",
    response_model=NextStepResponse,
    summary="Get the next recommendation, its explanation and the item to answer",
)
def next_step(user: ConsentedUser, svc: Svc) -> NextStepResponse:
    if svc.session.get(m.LearnerTraitsRow, user.id) is None:
        raise conflict("QUESTIONNAIRE_REQUIRED", "Please complete the questionnaire first")
    if (pending := _pending(svc, user.id)) is not None:
        return pending
    try:
        planner = svc.planner()
    except LookupError as err:
        raise conflict("NO_CONTENT", "No reviewed practice items are available yet") from err

    state = svc.learner_model.get_state(user.id)
    rec = planner.next_step(state)
    style, style_source = planner.choose_style(state, rec.target_concept_id)
    explanation = svc.explainer.explain(
        ExplanationRequest(
            user_id=user.id,
            recommendation_id=rec.id,
            concept_ids=[rec.target_concept_id],
            reasons=rec.reasons,
            style=style,
            style_source=style_source,
            followup_item_id=_microcheck(svc, user.id, rec.target_concept_id),
        )
    )
    svc.session.add(
        m.ExplanationRow(
            id=explanation.id,
            recommendation_id=rec.id,
            user_id=user.id,
            concept_ids=explanation.concept_ids,
            style=explanation.style.model_dump(mode="json"),
            style_source=explanation.style_source,
            body_markdown=explanation.body_markdown,
            source=explanation.source,
            followup_item_id=explanation.followup_item_id,
            prompt_version=explanation.prompt_version,
            model=explanation.model,
            latency_ms=explanation.latency_ms,
        )
    )
    svc.session.commit()
    item = svc.graph.get_item(rec.item_id) if rec.item_id else None
    return NextStepResponse(
        recommendation=rec, explanation=explanation, item=public(item) if item else None
    )
