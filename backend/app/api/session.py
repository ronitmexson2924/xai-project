"""Session management and recommendation routes.

Owner: Mit.
"""

import random
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import (
    ExplainerDep,
    FeedbackAnalyzerDep,
    GraphDep,
    LearnerModelDep,
    PlannerDep,
)
from app.auth import DbDep, LearnerDep
from app.contracts.explanation import ExplanationRequest
from app.contracts.graph import Item, PublicItem
from app.contracts.planning import NextStepResponse, Recommendation
from app.contracts.reasons import ReasonEvidence
from app.db import models as m
from app.telemetry import explanation_from_row

router = APIRouter(prefix="/session", tags=["session"])

# An unanswered recommendation is shown again (reload, second tab, double click) for this long;
# after that the learner gets a fresh one. Skipping by asking again is therefore not possible.
PENDING_TTL = timedelta(hours=2)


def public_item(item: Item, user_id: uuid.UUID) -> PublicItem:
    """The item without its answer. Options are shuffled per learner (stable across reloads):
    the bank must not leak the answer through its position."""
    options = list(item.options)
    random.Random(f"{user_id}:{item.id}").shuffle(options)
    return PublicItem(
        id=item.id, concept_id=item.concept_id, kind=item.kind, stem=item.stem, options=options
    )


def recommendation_from_row(row: m.RecommendationRow) -> Recommendation:
    return Recommendation(
        id=row.id,
        user_id=row.user_id,
        kind=row.kind,
        target_concept_id=row.target_concept_id,
        item_id=row.item_id,
        reasons=[ReasonEvidence.model_validate(r) for r in row.reasons],
        policy_version=row.policy_version,
    )


@router.post(
    "/next",
    response_model=NextStepResponse,
    summary="Get the next learning recommendation, explanation, and micro-check",
)
def next_step(
    current: LearnerDep,
    session: DbDep,
    graph: GraphDep,
    learner_model: LearnerModelDep,
    planner: PlannerDep,
    explainer: ExplainerDep,
    analyzer: FeedbackAnalyzerDep,
) -> NextStepResponse:
    pending = session.execute(
        select(m.RecommendationRow, m.ExplanationRow)
        .join(m.ExplanationRow, m.ExplanationRow.recommendation_id == m.RecommendationRow.id)
        .outerjoin(m.AttemptRow, m.AttemptRow.recommendation_id == m.RecommendationRow.id)
        .where(
            m.RecommendationRow.user_id == current.id,
            m.RecommendationRow.created_at > datetime.now(UTC) - PENDING_TTL,
            m.AttemptRow.id.is_(None),
        )
        .order_by(m.RecommendationRow.created_at.desc())
        .limit(1)
    ).one_or_none()
    if pending is not None:
        rec_row, explanation_row = pending
        try:
            item = graph.get_item(rec_row.item_id) if rec_row.item_id else None
        except KeyError:  # the item was withdrawn since; plan afresh below
            item = None
        if item is not None:
            return NextStepResponse(
                recommendation=recommendation_from_row(rec_row),
                explanation=explanation_from_row(explanation_row),
                item=public_item(item, current.id),
            )

    # The planner decides; the style comes from the planner too (it applies the learner's arm and
    # stores the style rationale), so what "Why this?" says is what actually happened.
    state = learner_model.get_state(current.id)
    rec = planner.next_step(state)
    style, style_source = planner.choose_style(state, rec.target_concept_id)
    explanation = explainer.explain(
        ExplanationRequest(
            user_id=current.id,
            recommendation_id=rec.id,
            concept_ids=[rec.target_concept_id],
            reasons=rec.reasons,
            style=style,
            style_source=style_source,
            followup_item_id=rec.item_id,
        )
    )
    analyzer.register(explanation)
    session.commit()
    return NextStepResponse(
        recommendation=rec,
        explanation=explanation,
        item=public_item(graph.get_item(rec.item_id), current.id) if rec.item_id else None,
    )
