"""HTTP routers and service wiring for PCG Engine API.

Owner: Mit. See tasks/mit.md and docs/API_CONTRACT.md.
"""

from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.attempts import router as attempts_router
from app.api.explanations import router as explanations_router
from app.api.graph import router as graph_router
from app.api.learners import router as learners_router
from app.api.model_insight import router as model_insight_router
from app.api.onboarding import router as onboarding_router
from app.api.ops import router as ops_router
from app.api.recommendations import router as recommendations_router
from app.api.report import router as report_router
from app.api.session import router as session_router
from app.api.tests_route import router as tests_router

api_router = APIRouter()

for router in (
    onboarding_router,
    session_router,
    attempts_router,
    explanations_router,
    recommendations_router,
    model_insight_router,
    learners_router,
    report_router,
    graph_router,
    tests_router,
    admin_router,
    ops_router,
):
    api_router.include_router(router)

__all__ = ["api_router"]
