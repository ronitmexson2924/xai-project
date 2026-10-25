"""Export the pilot logs as analysis-ready, pseudonymised data frames.

Learner ids are replaced by salted SHA-256 pseudonyms; emails and names are never read.
The predicted P(correct) for every attempt is recovered from the live model's own audit log
(state_updates: mastery *before* the attempt), so analyses use exactly what the system believed.
"""

import hashlib
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.graph import Item
from app.db import models as m
from app.graph.service import GraphSnapshot, is_test_item
from app.learner_model import bkt


@dataclass
class Frames:
    learners: pd.DataFrame  # learner, arm
    attempts: pd.DataFrame  # one row per answer, incl. p_hat and test phase
    explanations: pd.DataFrame  # one row per shown explanation + its feedback summary
    questionnaire: pd.DataFrame  # learner, item_id, value
    # XAI (docs/XAI_DESIGN.md §5): one row per recommendation, one per "Why this?" panel event
    recommendations: pd.DataFrame = field(default_factory=pd.DataFrame)
    xai_events: pd.DataFrame = field(default_factory=pd.DataFrame)

    def save(self, directory) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for name in (
            "learners",
            "attempts",
            "explanations",
            "questionnaire",
            "recommendations",
            "xai_events",
        ):
            getattr(self, name).to_csv(directory / f"{name}.csv", index=False)


def pseudonym(user_id, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()[:12]


def load_frames(
    session: Session, graph: GraphSnapshot, salt: str, email_like: str | None = None
) -> Frames:
    """Every non-deleted learner who has an experiment arm (optionally only emails LIKE a
    pattern, e.g. the simulator's '%@sim'; the email itself never leaves this function)."""
    query = (
        select(m.User.id, m.ExperimentAssignment.arm)
        .join(m.ExperimentAssignment, m.ExperimentAssignment.user_id == m.User.id)
        .where(m.User.deleted_at.is_(None))
    )
    if email_like is not None:
        query = query.where(m.User.email.like(email_like))
    learner_rows = session.execute(query).all()
    ids = {row.id: pseudonym(row.id, salt) for row in learner_rows}
    learners = pd.DataFrame(
        [{"learner": ids[r.id], "arm": r.arm} for r in learner_rows], columns=["learner", "arm"]
    )

    mastery_before = {}
    for row in session.scalars(
        select(m.StateUpdateRow).where(m.StateUpdateRow.source == "attempt")
    ):
        for concept, (before, _after) in row.delta.get("mastery_changes", {}).items():
            mastery_before[(row.source_id, concept)] = before

    # every item ever answered, whatever its review status now (rejected items included)
    items = {
        r.id: Item(
            id=r.id,
            concept_id=r.concept_id,
            kind=r.kind,
            stem=r.stem,
            options=r.options,
            answer=r.answer,
            is_microcheck=r.is_microcheck,
        )
        for r in session.scalars(select(m.ItemRow))
    }
    params = bkt.DEFAULT_PARAMS
    attempts = []
    for a in session.scalars(select(m.AttemptRow).order_by(m.AttemptRow.created_at)):
        if a.user_id not in ids:
            continue
        item = items[a.item_id]
        before = mastery_before.get((str(a.id), item.concept_id))
        attempts.append(
            {
                "learner": ids[a.user_id],
                "attempt_id": str(a.id),
                "item_id": a.item_id,
                "concept_id": item.concept_id,
                "cluster": graph.get_concept(item.concept_id).cluster,
                "created_at": a.created_at,
                "correct": bool(a.correct),
                "latency_ms": a.latency_ms,
                "confidence": a.confidence,
                "explanation_id": str(a.explanation_id) if a.explanation_id else None,
                "is_microcheck": item.is_microcheck,
                "test_phase": a.item_id.split("-", 1)[0] if is_test_item(a.item_id) else None,
                "mastery_before": before,
                "p_hat": None
                if before is None
                else bkt.predict_correct(before, params.p_slip, bkt.guess_for(item, params)),
            }
        )

    feedback = {
        str(r.explanation_id): (r.summary, r.applied_at)
        for r in session.scalars(select(m.ExplanationFeedbackRow))
    }
    explanations = []
    for e in session.scalars(select(m.ExplanationRow).order_by(m.ExplanationRow.created_at)):
        if e.user_id not in ids:
            continue
        s, feedback_at = feedback.get(str(e.id), ({}, None))
        explanations.append(
            {
                "learner": ids[e.user_id],
                "explanation_id": str(e.id),
                "concept_id": e.concept_ids[0],
                "created_at": e.created_at,
                "style_source": e.style_source,
                "example_first": e.style.get("example_first"),
                "length": e.style.get("length"),
                "depth": e.style.get("depth"),
                "has_feedback": bool(s),
                "feedback_at": feedback_at,  # when the summary was final (applied)
                "dwell_ms": s.get("effective_dwell_ms"),
                "expanded": s.get("expanded"),
                "replays": s.get("replays"),
                "clarity": s.get("clarity_rating"),
                "followup_correct": s.get("followup_correct"),
                "dismissed": s.get("dismissed_quickly"),
            }
        )

    questionnaire = pd.DataFrame(
        [
            {"learner": ids[r.user_id], "item_id": r.item_id, "value": r.value}
            for r in session.scalars(select(m.QuestionnaireResponseRow))
            if r.user_id in ids
        ],
        columns=["learner", "item_id", "value"],
    )
    recommendations = pd.DataFrame(
        [
            {
                "learner": ids[r.user_id],
                "recommendation_id": str(r.id),
                "created_at": r.created_at,
                "kind": r.kind,
                "rule": (r.rationale or {}).get("rule"),
                "has_rationale": r.rationale is not None,
                "n_counterfactuals": len((r.rationale or {}).get("counterfactuals", [])),
                "style_source": (r.style_rationale or {}).get("source"),
                "style_confidence": (r.style_rationale or {}).get("confidence"),
            }
            for r in session.scalars(select(m.RecommendationRow))
            if r.user_id in ids
        ],
        columns=[
            "learner",
            "recommendation_id",
            "created_at",
            "kind",
            "rule",
            "has_rationale",
            "n_counterfactuals",
            "style_source",
            "style_confidence",
        ],
    )
    xai_events = pd.DataFrame(
        [
            {
                "learner": ids[ev.user_id],
                "explanation_id": str(ev.explanation_id),
                "type": ev.type,
                "helpful": ev.payload.get("helpful") if ev.type == "why_rated" else None,
            }
            for ev in session.scalars(
                select(m.ExplanationEventRow).where(
                    m.ExplanationEventRow.type.in_(("why_opened", "why_rated"))
                )
            )
            if ev.user_id in ids
        ],
        columns=["learner", "explanation_id", "type", "helpful"],
    )
    return Frames(
        learners=learners,
        attempts=pd.DataFrame(attempts),
        explanations=pd.DataFrame(explanations),
        questionnaire=questionnaire,
        recommendations=recommendations,
        xai_events=xai_events,
    )
