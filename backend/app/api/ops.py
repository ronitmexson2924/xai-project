"""Pilot operations status (Task M8, admin accounts only).

Owner: Mit.

    python -m app.api.ops         prints the same report from the command line

Every figure is read from the database; latency comes from stored explanation timings. Nothing is
asserted that was not measured.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.auth import AdminDep, DbDep
from app.config import settings
from app.db import models as m

router = APIRouter(prefix="/ops", tags=["ops"])

EXPLANATION_P95_BUDGET_MS = 300  # ARCHITECTURE.md latency budget for /session/next


class OpsHealthResponse(BaseModel):
    last_checked_utc: str
    concepts_count: int
    approved_items_count: int
    draft_items_count: int
    active_learners_24h: int
    registered_learners: int
    explanation_p95_ms_24h: float | None
    explanation_p95_budget_ms: int
    rate_limiter_enabled: bool


def get_pilot_ops_status(session: Session) -> OpsHealthResponse:
    since = datetime.now(UTC) - timedelta(hours=24)

    def items(status: str) -> int:
        return session.scalar(
            select(func.count()).select_from(m.ItemRow).where(m.ItemRow.review_status == status)
        )

    return OpsHealthResponse(
        last_checked_utc=datetime.now(UTC).isoformat(),
        concepts_count=session.scalar(select(func.count()).select_from(m.ConceptRow)),
        approved_items_count=items("approved"),
        draft_items_count=items("draft"),
        active_learners_24h=session.scalar(
            select(func.count(distinct(m.AttemptRow.user_id))).where(
                m.AttemptRow.created_at >= since
            )
        ),
        registered_learners=session.scalar(
            select(func.count())
            .select_from(m.User)
            .where(m.User.is_admin.is_(False), m.User.deleted_at.is_(None))
        ),
        explanation_p95_ms_24h=session.scalar(
            select(func.percentile_cont(0.95).within_group(m.ExplanationRow.latency_ms)).where(
                m.ExplanationRow.created_at >= since
            )
        ),
        explanation_p95_budget_ms=EXPLANATION_P95_BUDGET_MS,
        rate_limiter_enabled=settings.rate_limit_enabled,
    )


@router.get("/status", response_model=OpsHealthResponse, summary="Pilot operations status")
def ops_status(_: AdminDep, session: DbDep) -> OpsHealthResponse:
    return get_pilot_ops_status(session)


def main() -> None:
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        status = get_pilot_ops_status(session)
    for field, value in status.model_dump().items():
        print(f"{field:28} {value}")


if __name__ == "__main__":
    main()
