"""Administrative metrics and research export routes (admin accounts only).

Owner: Mit.
"""

import csv
import io
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import Float, Integer, cast, distinct, func, select

from app.api.errors import api_error
from app.api.schemas import AdminMetricsResponse
from app.auth import AdminDep, DbDep
from app.config import settings
from app.db import models as m
from app.graph.service import TEST_ITEM_PREFIXES
from app.pseudonyms import pseudonym  # the same ids as research/analysis/export.py

router = APIRouter(prefix="/admin", tags=["admin"])

ExportTable = Literal["users", "assignments", "attempts"]


def _cell(value) -> str:
    """CSV cell that spreadsheets will not execute as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _learners():
    """Active learner accounts (admins and withdrawn accounts are not study data)."""
    return (m.User.is_admin.is_(False)) & (m.User.deleted_at.is_(None))


@router.get("/metrics", response_model=AdminMetricsResponse, summary="Study and system metrics")
def get_metrics(_: AdminDep, session: DbDep) -> AdminMetricsResponse:
    learners = _learners()
    arms = dict(
        session.execute(
            select(m.ExperimentAssignment.arm, func.count())
            .join(m.User, m.User.id == m.ExperimentAssignment.user_id)
            .where(learners)
            .group_by(m.ExperimentAssignment.arm)
        ).all()
    )
    total_users = session.scalar(select(func.count()).select_from(m.User).where(learners))
    consented = session.scalar(
        select(func.count()).select_from(m.User).where(learners, m.User.consent_at.is_not(None))
    )
    attempts = session.scalar(
        select(func.count())
        .select_from(m.AttemptRow)
        .join(m.User, m.User.id == m.AttemptRow.user_id)
        .where(learners)
    )
    p50, p95, n_explanations = session.execute(
        select(
            func.percentile_cont(0.5).within_group(m.ExplanationRow.latency_ms),
            func.percentile_cont(0.95).within_group(m.ExplanationRow.latency_ms),
            func.count(),
        )
    ).one()
    sources = dict(
        session.execute(
            select(m.ExplanationRow.source, func.count()).group_by(m.ExplanationRow.source)
        ).all()
    )
    rating = cast(m.ExplanationFeedbackRow.summary["clarity_rating"].astext, Integer)
    clarity = dict(
        session.execute(
            select(rating, func.count()).where(rating.is_not(None)).group_by(rating)
        ).all()
    )
    avg_dwell = session.scalar(
        select(func.avg(cast(m.ExplanationFeedbackRow.summary["effective_dwell_ms"].astext, Float)))
    )

    def submissions(prefix: str) -> int:
        return session.scalar(
            select(func.count(distinct(m.AttemptRow.user_id))).where(
                m.AttemptRow.item_id.startswith(prefix)
            )
        )

    return AdminMetricsResponse(
        total_users=total_users,
        consented_users=consented,
        arm_distribution={
            arm: arms.get(arm, 0) for arm in ("generic", "static_personalized", "closed_loop")
        },
        total_attempts=attempts,
        total_explanations=n_explanations,
        p50_explanation_latency_ms=p50,
        p95_explanation_latency_ms=p95,
        source_mix={s: sources.get(s, 0) for s in ("precomputed", "llm", "template")},
        clarity_distribution={r: clarity.get(r, 0) for r in range(1, 6)},
        avg_dwell_ms=avg_dwell,
        pretest_submissions=submissions(TEST_ITEM_PREFIXES[0]),
        posttest_submissions=submissions(TEST_ITEM_PREFIXES[1]),
    )


@router.get("/export.csv", summary="Pseudonymised research export (one table per request)")
def export_csv(
    _: AdminDep,
    session: DbDep,
    table: Annotated[ExportTable, Query()] = "users",
) -> Response:
    salt = settings.analysis_salt
    if not salt:
        raise api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "EXPORT_DISABLED",
            "Set ANALYSIS_SALT on the server to enable pseudonymised exports",
        )
    output = io.StringIO()
    writer = csv.writer(output)
    learners = _learners()
    if table == "users":
        writer.writerow(["pseudonym_id", "created_at", "consented", "arm"])
        rows = session.execute(
            select(m.User.id, m.User.created_at, m.User.consent_at, m.ExperimentAssignment.arm)
            .outerjoin(m.ExperimentAssignment, m.ExperimentAssignment.user_id == m.User.id)
            .where(learners)
            .order_by(m.User.created_at)
        )
        for user_id, created, consent, arm in rows:
            writer.writerow(
                [pseudonym(user_id, salt), created.isoformat(), consent is not None, arm]
            )
    elif table == "assignments":
        writer.writerow(["pseudonym_id", "arm", "assigned_at"])
        rows = session.execute(
            select(m.ExperimentAssignment)
            .join(m.User, m.User.id == m.ExperimentAssignment.user_id)
            .where(learners)
            .order_by(m.ExperimentAssignment.assigned_at)
        ).scalars()
        for a in rows:
            writer.writerow([pseudonym(a.user_id, salt), a.arm, a.assigned_at.isoformat()])
    else:
        writer.writerow(
            [
                "attempt_id",
                "pseudonym_id",
                "item_id",
                "concept_id",
                "correct",
                "latency_ms",
                "hints_used",
                "confidence",
                "created_at",
            ]
        )
        rows = session.execute(
            select(m.AttemptRow, m.ItemRow.concept_id)
            .join(m.User, m.User.id == m.AttemptRow.user_id)
            .join(m.ItemRow, m.ItemRow.id == m.AttemptRow.item_id)
            .where(learners)
            .order_by(m.AttemptRow.created_at)
        )
        for a, concept_id in rows:
            writer.writerow(
                [
                    a.id,
                    pseudonym(a.user_id, salt),
                    _cell(a.item_id),
                    _cell(concept_id),
                    a.correct,
                    a.latency_ms,
                    a.hints_used,
                    "" if a.confidence is None else a.confidence,
                    a.created_at.isoformat(),
                ]
            )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{table}_export.csv"',
            "Cache-Control": "no-store",
        },
    )
