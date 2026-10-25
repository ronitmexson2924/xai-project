"""Per-request wiring of the real services (tasks/ronit.md "Asks for Mit").

One database session per request (`DbSession`); handlers commit explicitly once their work
succeeded, and anything uncommitted is rolled back when the session closes. The concept graph is
an immutable snapshot built once per process.
"""

import threading
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.db import DbSession, get_session
from app.config import settings
from app.explainer import GroundedExplainerService
from app.explainer.store import DbVariantStore
from app.graph.service import GraphSnapshot
from app.learner_model.service import LearnerModel
from app.planner.service import Planner
from app.planner.xai import Explainability
from app.telemetry import TelemetryFeedbackAnalyzer

__all__ = ["DbSession", "Graph", "Services", "Svc", "get_session", "load_graph", "set_graph"]


_graph: GraphSnapshot | None = None
_graph_lock = threading.Lock()


def load_graph(session: Session) -> GraphSnapshot:
    global _graph
    with _graph_lock:
        if _graph is None:
            _graph = GraphSnapshot.from_db(session, include_drafts=settings.include_draft_items)
        return _graph


def set_graph(graph: GraphSnapshot | None) -> None:
    """Replace the cached snapshot (tests, or after re-seeding content)."""
    global _graph
    with _graph_lock:
        _graph = graph


def get_graph(session: DbSession) -> GraphSnapshot:
    return _graph if _graph is not None else load_graph(session)


Graph = Annotated[GraphSnapshot, Depends(get_graph)]


class Services:
    """Everything one request needs, sharing its session."""

    def __init__(self, session: Session, graph: GraphSnapshot) -> None:
        self.session = session
        self.graph = graph
        self.learner_model = LearnerModel(session, graph)
        self.xai = Explainability(self.learner_model)
        self.analyzer = TelemetryFeedbackAnalyzer(session)
        self.explainer = GroundedExplainerService(graph, store=DbVariantStore(session))

    def planner(self) -> Planner:
        # built on demand: it refuses to start when no practice items are available
        return Planner(self.session, self.graph, self.learner_model)


def get_services(session: DbSession, graph: Graph) -> Services:
    return Services(session, graph)


Svc = Annotated[Services, Depends(get_services)]
