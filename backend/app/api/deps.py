"""Dependency injection for the domain services.

Owner: Mit.
Every request gets the real, database-backed services from app.contracts.services:
GraphSnapshot (app/graph), LearnerModel (app/learner_model), Planner and Explainability
(app/planner), the grounded explainer (app/explainer) and the Postgres telemetry analyzer
(app/telemetry). All of them share the request's Session, so one request is one transaction.

The concept graph is read from the database once per process (content changes only through
`python -m app.graph.seed`, after which the API is restarted, or `reload_graph()` is called).
"""

from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import DbDep
from app.config import settings
from app.explainer import DbVariantStore, GroundedExplainerService
from app.graph.service import GraphSnapshot
from app.learner_model.service import LearnerModel
from app.planner.service import Planner
from app.planner.xai import Explainability
from app.telemetry import DbFeedbackAnalyzer

_lock = Lock()
_graph: GraphSnapshot | None = None


def _load(session: Session) -> GraphSnapshot:
    global _graph
    with _lock:
        if _graph is None:
            graph = GraphSnapshot.from_db(session, include_drafts=settings.include_draft_items)
            if not graph.practice_concepts:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "error": {
                            "code": "CONTENT_NOT_SEEDED",
                            "message": "No approved items yet (review content/items, S3)",
                        }
                    },
                )
            _graph = graph
        return _graph


def reload_graph() -> None:
    """Forget the cached graph; the next request reads it again."""
    global _graph
    with _lock:
        _graph = None


def get_graph(session: DbDep) -> GraphSnapshot:
    return _graph if _graph is not None else _load(session)


GraphDep = Annotated[GraphSnapshot, Depends(get_graph)]


def get_learner_model(session: DbDep, graph: GraphDep) -> LearnerModel:
    return LearnerModel(session, graph)


LearnerModelDep = Annotated[LearnerModel, Depends(get_learner_model)]


def get_planner(session: DbDep, graph: GraphDep, model: LearnerModelDep) -> Planner:
    return Planner(session, graph, model)


def get_explainability(model: LearnerModelDep) -> Explainability:
    return Explainability(model)


def get_explainer(session: DbDep, graph: GraphDep) -> GroundedExplainerService:
    # precomputed variants are read from explanation_variants (python -m app.explainer.precompute)
    return GroundedExplainerService(graph, store=DbVariantStore(session))


def get_feedback_analyzer(session: DbDep) -> DbFeedbackAnalyzer:
    return DbFeedbackAnalyzer(session)


PlannerDep = Annotated[Planner, Depends(get_planner)]
ExplainabilityDep = Annotated[Explainability, Depends(get_explainability)]
ExplainerDep = Annotated[GroundedExplainerService, Depends(get_explainer)]
FeedbackAnalyzerDep = Annotated[DbFeedbackAnalyzer, Depends(get_feedback_analyzer)]
