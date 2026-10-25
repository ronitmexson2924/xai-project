"""Admin: operational metrics and pseudonymised research exports. Admins only
(users.is_admin, granted with `python -m app.auth.admin_cli grant <email>`).

Owner: Mit.
"""

import csv
import hashlib
import hmac
import io
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.api.errors import api_error
from app.api.schemas import AdminMetricsResponse
from app.auth import AdminUser
from app.config import settings
from app.db import models as m

router = APIRouter(prefix="/admin", tags=["admin"])

ExportTable = Literal["users", "attempts", "explanations", "feedback"]


def _percentile(values: list[int], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return float(values[lo] + (values[hi] - values[lo]) * (k - lo))


@router.get("/metrics", response_model=AdminMetricsResponse, summary="Operational metrics")
def get_metrics(_: AdminUser, session: DbSession) -> AdminMetricsResponse:
    active = m.User.deleted_at.is_(None)
    arms = dict(
        session.execute(
            select(m.ExperimentAssignment.arm, func.count())
            .join(m.User, m.User.id == m.ExperimentAssignment.user_id)
            .where(active)
            .group_by(m.ExperimentAssignment.arm)
        ).all()
    )
    latencies = list(session.scalars(select(m.ExplanationRow.latency_ms)))
    sources = dict(
        session.execute(
            select(m.ExplanationRow.source, func.count()).group_by(m.ExplanationRow.source)
        ).all()
    )
    clarity = dict.fromkeys(range(1, 6), 0)
    dwell = []
    for summary in session.scalars(select(m.ExplanationFeedbackRow.summary)):
        if (rating := summary.get("clarity_rating")) in clarity:
            clarity[rating] += 1
        if summary.get("effective_dwell_ms") is not None:
            dwell.append(summary["effective_dwell_ms"])
    return AdminMetricsResponse(
        total_users=session.scalar(select(func.count()).select_from(m.User).where(active)) or 0,
        consented_users=session.scalar(
            select(func.count()).select_from(m.User).where(active, m.User.consent_at.is_not(None))
        )
        or 0,
        arm_distribution={
            arm: arms.get(arm, 0) for arm in ("generic", "static_personalized", "closed_loop")
        },
        total_attempts=session.scalar(select(func.count()).select_from(m.AttemptRow)) or 0,
        total_explanations=len(latencies),
        p50_latency_ms=_percentile(latencies, 0.5),
        p95_latency_ms=_percentile(latencies, 0.95),
        source_mix={s: sources.get(s, 0) for s in ("precomputed", "llm", "template")},
        clarity_distribution=clarity,
        avg_dwell_ms=sum(dwell) / len(dwell) if dwell else None,
    )


def pseudonym(user_id) -> str:  # noqa: ANN001
    return hmac.new(
        settings.export_salt.encode(), str(user_id).encode(), hashlib.sha256
    ).hexdigest()[:16]


def _cell(value: object) -> object:
    """Neutralise spreadsheet formulas (CSV injection): text starting with = + - @ is quoted."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


@router.get("/export.csv", summary="Pseudonymised CSV export of one table")
def export_csv(
    _: AdminUser,
    session: DbSession,
    table: Annotated[ExportTable, Query()] = "users",
) -> Response:
    if len(settings.export_salt) < 16:
        raise api_error(
            503, "EXPORT_DISABLED", "Set EXPORT_SALT (16+ characters) to enable exports"
        )
    deleted = set(session.scalars(select(m.User.id).where(m.User.deleted_at.is_not(None))))
    out = io.StringIO()
    writer = csv.writer(out)
    if table == "users":
        writer.writerow(["learner", "arm", "created_at", "consented"])
        for user, arm in session.execute(
            select(m.User, m.ExperimentAssignment.arm).join(
                m.ExperimentAssignment, m.ExperimentAssignment.user_id == m.User.id
            )
        ):
            if user.id not in deleted:
                writer.writerow(
                    [pseudonym(user.id), arm, _cell(user.created_at), user.consent_at is not None]
                )
    elif table == "attempts":
        writer.writerow(
            [
                "learner",
                "item_id",
                "correct",
                "latency_ms",
                "hints_used",
                "confidence",
                "created_at",
            ]
        )
        for a in session.scalars(select(m.AttemptRow).order_by(m.AttemptRow.created_at)):
            if a.user_id not in deleted:
                writer.writerow(
                    [
                        pseudonym(a.user_id),
                        _cell(a.item_id),
                        a.correct,
                        a.latency_ms,
                        a.hints_used,
                        a.confidence,
                        _cell(a.created_at),
                    ]
                )
    elif table == "explanations":
        writer.writerow(
            [
                "learner",
                "explanation_id",
                "concept_id",
                "source",
                "style_source",
                "latency_ms",
                "created_at",
            ]
        )
        for e in session.scalars(select(m.ExplanationRow).order_by(m.ExplanationRow.created_at)):
            if e.user_id not in deleted:
                writer.writerow(
                    [
                        pseudonym(e.user_id),
                        e.id,
                        _cell(e.concept_ids[0]),
                        e.source,
                        e.style_source,
                        e.latency_ms,
                        _cell(e.created_at),
                    ]
                )
    else:
        writer.writerow(
            [
                "learner",
                "explanation_id",
                "dwell_ms",
                "clarity",
                "followup_correct",
                "dismissed_quickly",
                "applied_at",
            ]
        )
        for f, user_id in session.execute(
            select(m.ExplanationFeedbackRow, m.ExplanationRow.user_id).join(
                m.ExplanationRow, m.ExplanationRow.id == m.ExplanationFeedbackRow.explanation_id
            )
        ):
            if user_id not in deleted:
                s = f.summary
                writer.writerow(
                    [
                        pseudonym(user_id),
                        f.explanation_id,
                        s.get("effective_dwell_ms"),
                        s.get("clarity_rating"),
                        s.get("followup_correct"),
                        s.get("dismissed_quickly"),
                        _cell(f.applied_at),
                    ]
                )
    return Response(
        content=out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{table}_export.csv"'},
    )
