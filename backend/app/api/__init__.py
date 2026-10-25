"""HTTP routers and service wiring for PCG Engine API.

Owner: Mit. See tasks/mit.md and docs/API_CONTRACT.md.
"""

from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.attempts import router as attempts_router
from app.api.explanations import router as explanations_router
from app.api.graph import router as graph_router
from app.api.learners import router as learners_router
from app.api.onboarding import router as onboarding_router
from app.api.session import router as session_router

api_router = APIRouter()

api_router.include_router(onboarding_router)
api_router.include_router(session_router)
api_router.include_router(attempts_router)
api_router.include_router(explanations_router)
api_router.include_router(learners_router)
api_router.include_router(graph_router)
api_router.include_router(admin_router)

__all__ = ["api_router"]
