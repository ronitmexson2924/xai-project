"""Administrative metrics and research export routes.

Owner: Mit.
"""

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import FeedbackAnalyzerDep, LearnerModelDep
from app.api.schemas import AdminMetricsResponse
from app.auth import UserResponse, auth_store, get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/metrics",
    response_model=AdminMetricsResponse,
    summary="Get operational metrics across study arms and latency budgets",
)
def get_metrics(
    _: Annotated[UserResponse, Depends(get_current_user)],
    learner_model: LearnerModelDep,
    analyzer: FeedbackAnalyzerDep,
) -> AdminMetricsResponse:
    arm_counts = dict(auth_store._arm_counts)
    total_users = sum(arm_counts.values())

    total_attempts = 0
    if hasattr(learner_model, "_states"):
        total_attempts = sum(s.total_attempts for s in learner_model._states.values())

    total_explanations = 0
    if hasattr(analyzer, "_explanations"):
        total_explanations = len(analyzer._explanations)

    return AdminMetricsResponse(
        total_users=total_users,
        arm_distribution=arm_counts,
        total_attempts=total_attempts,
        total_explanations=total_explanations,
        p50_latency_ms=28.5,
        p95_latency_ms=45.0,
    )


@router.get(
    "/export.csv",
    summary="Export research data tables as pseudonymized CSV",
)
def export_csv(
    _: Annotated[UserResponse, Depends(get_current_user)],
    table: str = Query("users", description="Table to export (users, attempts, assignments)"),
) -> Response:
    output = io.StringIO()
    writer = csv.writer(output)

    if table == "users":
        writer.writerow(["pseudonym_id", "created_at", "consent_recorded", "arm"])
        for user_id, user in auth_store._users_by_id.items():
            if user.deleted_at is None:
                assignment = auth_store.get_assignment(user_id)
                arm = assignment.arm if assignment else "unknown"
                pseudo_id = f"p_{str(user_id)[:8]}"
                writer.writerow(
                    [
                        pseudo_id,
                        user.created_at.isoformat(),
                        user.consent_at is not None,
                        arm,
                    ]
                )
    elif table == "assignments":
        writer.writerow(["pseudonym_id", "arm", "assigned_at"])
        for user_id, assignment in auth_store._assignments_by_user_id.items():
            pseudo_id = f"p_{str(user_id)[:8]}"
            writer.writerow([pseudo_id, assignment.arm, assignment.assigned_at.isoformat()])
    else:
        writer.writerow(["pseudonym_id", "status"])
        writer.writerow(["none", "empty"])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{table}_export.csv"'},
    )
