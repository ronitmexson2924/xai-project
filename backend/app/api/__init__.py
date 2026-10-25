"""HTTP routers (docs/API_CONTRACT.md). Owner: Mit."""

from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.attempts import router as attempts_router
from app.api.explanations import router as explanations_router
from app.api.graph import router as graph_router
from app.api.items import router as items_router
from app.api.items import tests_router
from app.api.learners import router as learners_router
from app.api.onboarding import router as onboarding_router
from app.api.recommendations import router as recommendations_router
from app.api.session import router as session_router

api_router = APIRouter()
for router in (
    onboarding_router,
    session_router,
    attempts_router,
    explanations_router,
    recommendations_router,
    items_router,
    tests_router,
    learners_router,
    graph_router,
    admin_router,
):
    api_router.include_router(router)

__all__ = ["api_router"]
