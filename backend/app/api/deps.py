"""Dependency injection for domain services.

Owner: Mit.
Provides instances of domain service Protocols from app.contracts.services.
Uses fakes from app.contracts.fakes now; real implementations will be swapped in
with a single line here as Ronit merges R0, R1, R2.
"""

from typing import Annotated

from fastapi import Depends

from app.contracts.fakes import (
    FakeExplainer,
    FakeFeedbackAnalyzer,
    FakeGraph,
    FakeLearnerModel,
    FakePlanner,
)
from app.contracts.services import (
    ExplainerService,
    FeedbackAnalyzer,
    GraphService,
    LearnerModelService,
    PlannerService,
)

# Singletons for development and testing with fakes
_graph_service: GraphService = FakeGraph()
_learner_model_service: LearnerModelService = FakeLearnerModel()
_planner_service: PlannerService = FakePlanner(FakeGraph())
_explainer_service: ExplainerService = FakeExplainer(FakeGraph())
_feedback_analyzer: FeedbackAnalyzer = FakeFeedbackAnalyzer()


def get_graph_service() -> GraphService:
    return _graph_service


def get_learner_model_service() -> LearnerModelService:
    return _learner_model_service


def get_planner_service() -> PlannerService:
    return _planner_service


def get_explainer_service() -> ExplainerService:
    return _explainer_service


def get_feedback_analyzer() -> FeedbackAnalyzer:
    return _feedback_analyzer


def reset_services() -> None:
    """Reset fakes between tests to ensure test isolation."""
    global _graph_service, _learner_model_service, _planner_service
    global _explainer_service, _feedback_analyzer

    graph = FakeGraph()
    _graph_service = graph
    _learner_model_service = FakeLearnerModel()
    _planner_service = FakePlanner(graph)
    _explainer_service = FakeExplainer(graph)
    _feedback_analyzer = FakeFeedbackAnalyzer()


# Typed Dependency Shortcuts for Route Handlers
GraphDep = Annotated[GraphService, Depends(get_graph_service)]
LearnerModelDep = Annotated[LearnerModelService, Depends(get_learner_model_service)]
PlannerDep = Annotated[PlannerService, Depends(get_planner_service)]
ExplainerDep = Annotated[ExplainerService, Depends(get_explainer_service)]
FeedbackAnalyzerDep = Annotated[FeedbackAnalyzer, Depends(get_feedback_analyzer)]
