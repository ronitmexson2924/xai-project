"""The learner report's Explainability section (task R13), for the learner and for admins.

A learner sees only their own report. Admins can list learners by pseudonym (never by name or
email) and open any learner's report, plus the cross-learner SHAP view, which identifies no one.
"""

from datetime import datetime

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import GraphDep, LearnerModelDep
from app.api.errors import api_error, not_found
from app.auth import AdminDep, DbDep, LearnerDep
from app.config import settings
from app.db import models as m
from app.pseudonyms import pseudonym
from app.xai import GlobalAttributions, UserReport, explain_user, global_attributions

router = APIRouter(tags=["xai"])


@router.get(
    "/learners/me/report",
    response_model=UserReport,
    summary="Your report's Explainability section: why the model predicts what it does for you",
)
def my_report(
    current: LearnerDep, session: DbDep, graph: GraphDep, learner_model: LearnerModelDep
) -> UserReport:
    return explain_user(session, graph, learner_model, current.id)


class LearnerListing(BaseModel):
    pseudonym: str
    arm: str
    attempts: int
    last_active: datetime | None


def _salt() -> str:
    if not settings.analysis_salt:
        raise api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "PSEUDONYMS_DISABLED",
            "Set ANALYSIS_SALT on the server to list learners by pseudonym",
        )
    return settings.analysis_salt


def _learner_rows(session: DbDep):
    return session.execute(
        select(
            m.User.id,
            m.ExperimentAssignment.arm,
            func.count(m.AttemptRow.id),
            func.max(m.AttemptRow.created_at),
        )
        .join(m.ExperimentAssignment, m.ExperimentAssignment.user_id == m.User.id)
        .outerjoin(m.AttemptRow, m.AttemptRow.user_id == m.User.id)
        .where(m.User.is_admin.is_(False), m.User.deleted_at.is_(None))
        .group_by(m.User.id, m.ExperimentAssignment.arm)
        .order_by(func.max(m.AttemptRow.created_at).desc().nulls_last())
    ).all()


@router.get(
    "/admin/learners",
    response_model=list[LearnerListing],
    summary="Learners by pseudonym, most recently active first (admins only)",
)
def list_learners(_: AdminDep, session: DbDep) -> list[LearnerListing]:
    salt = _salt()
    return [
        LearnerListing(pseudonym=pseudonym(uid, salt), arm=arm, attempts=n, last_active=last)
        for uid, arm, n, last in _learner_rows(session)
    ]


@router.get(
    "/admin/learners/{learner_pseudonym}/report",
    response_model=UserReport,
    summary="One learner's report, by pseudonym (admins only)",
)
def learner_report(
    learner_pseudonym: str,
    _: AdminDep,
    session: DbDep,
    graph: GraphDep,
    learner_model: LearnerModelDep,
) -> UserReport:
    salt = _salt()
    for uid, *_rest in _learner_rows(session):
        if pseudonym(uid, salt) == learner_pseudonym:
            return explain_user(session, graph, learner_model, uid)
    raise not_found("learner")


@router.get(
    "/admin/xai/global",
    response_model=GlobalAttributions,
    summary="SHAP across learners' recent predictions, for a beeswarm (admins only, anonymous)",
)
def global_view(_: AdminDep, session: DbDep, graph: GraphDep) -> GlobalAttributions:
    return global_attributions(session, graph)
