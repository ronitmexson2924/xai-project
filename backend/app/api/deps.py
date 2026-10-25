"""Dependency injection for domain services.

Owner: Mit.
Provides instances of domain service Protocols from app.contracts.services.
Uses fakes from app.contracts.fakes now; real implementations will be swapped in
with a single line here as Ronit merges R0, R1, R2.
"""

from typing import Annotated

from fastapi import Depends

from app.api.graph_service import CurriculumGraphService
from app.auth.store import DEMO_ADVANCED_ID, DEMO_INTERMEDIATE_ID, DEMO_NOVICE_ID
from app.contracts.fakes import (
    FakeLearnerModel,
    FakePlanner,
)
from app.contracts.learner import (
    AffectiveState,
    ConceptMastery,
    LearnerState,
    LearnerTraits,
    TraitEstimate,
)
from app.contracts.services import (
    ExplainerService,
    FeedbackAnalyzer,
    GraphService,
    LearnerModelService,
    PlannerService,
)
from app.explainer import GroundedExplainerService
from app.items.curriculum import get_all_concepts
from app.telemetry import TelemetryFeedbackAnalyzer


def seed_demo_learner_states(learner_model: LearnerModelService) -> None:
    """Populates realistic demo learner profiles across beginner, intermediate, and advanced."""
    if not hasattr(learner_model, "_states"):
        return

    # 1. Novice (Ada Lovelace)
    novice_traits = LearnerTraits(
        traits={
            "abstraction_preference": TraitEstimate(mean=0.18, variance=0.03, n_observations=6),
            "load_tolerance": TraitEstimate(mean=0.32, variance=0.04, n_observations=5),
            "depth_preference": TraitEstimate(mean=0.28, variance=0.03, n_observations=5),
            "persistence": TraitEstimate(mean=0.82, variance=0.02, n_observations=8),
            "self_efficacy": TraitEstimate(mean=0.42, variance=0.05, n_observations=4),
        }
    )
    novice_mastery = {
        "loops": ConceptMastery(concept_id="loops", p_mastery=0.65, n_attempts=4),
        "nested-loops": ConceptMastery(concept_id="nested-loops", p_mastery=0.35, n_attempts=2),
        "recursion-base-case": ConceptMastery(
            concept_id="recursion-base-case",
            p_mastery=0.22,
            n_attempts=3,
            misconception_ids=["recursion-never-halts"],
            misconception_suspicion=0.75,
        ),
        "array-indexing": ConceptMastery(concept_id="array-indexing", p_mastery=0.50, n_attempts=2),
    }
    learner_model._states[DEMO_NOVICE_ID] = LearnerState(
        user_id=DEMO_NOVICE_ID,
        arm="closed_loop",
        mastery=novice_mastery,
        traits=novice_traits,
        affect=AffectiveState(engagement=0.85, frustration=0.20, fatigue=0.10),
        total_attempts=11,
    )

    # 2. Intermediate (Alan Turing)
    inter_traits = LearnerTraits(
        traits={
            "abstraction_preference": TraitEstimate(mean=0.52, variance=0.02, n_observations=15),
            "load_tolerance": TraitEstimate(mean=0.65, variance=0.02, n_observations=12),
            "depth_preference": TraitEstimate(mean=0.72, variance=0.01, n_observations=14),
            "persistence": TraitEstimate(mean=0.78, variance=0.02, n_observations=16),
            "self_efficacy": TraitEstimate(mean=0.70, variance=0.02, n_observations=12),
        }
    )
    inter_mastery = {
        "loops": ConceptMastery(concept_id="loops", p_mastery=0.95, n_attempts=6),
        "nested-loops": ConceptMastery(concept_id="nested-loops", p_mastery=0.90, n_attempts=4),
        "conditional-invariants": ConceptMastery(
            concept_id="conditional-invariants", p_mastery=0.88, n_attempts=4
        ),
        "array-indexing": ConceptMastery(concept_id="array-indexing", p_mastery=0.88, n_attempts=5),
        "two-pointers-technique": ConceptMastery(
            concept_id="two-pointers-technique", p_mastery=0.82, n_attempts=4
        ),
        "sliding-window": ConceptMastery(concept_id="sliding-window", p_mastery=0.75, n_attempts=3),
        "prefix-sums": ConceptMastery(concept_id="prefix-sums", p_mastery=0.80, n_attempts=3),
        "singly-linked-list-node": ConceptMastery(
            concept_id="singly-linked-list-node", p_mastery=0.85, n_attempts=4
        ),
        "linked-list-traversal": ConceptMastery(
            concept_id="linked-list-traversal", p_mastery=0.80, n_attempts=3
        ),
        "fast-slow-pointers": ConceptMastery(
            concept_id="fast-slow-pointers", p_mastery=0.72, n_attempts=3
        ),
        "recursion-base-case": ConceptMastery(
            concept_id="recursion-base-case", p_mastery=0.78, n_attempts=4
        ),
        "recursive-call-stack": ConceptMastery(
            concept_id="recursive-call-stack", p_mastery=0.65, n_attempts=3
        ),
        "binary-tree-traversal-preorder": ConceptMastery(
            concept_id="binary-tree-traversal-preorder", p_mastery=0.55, n_attempts=2
        ),
        "bst-search-property": ConceptMastery(
            concept_id="bst-search-property", p_mastery=0.50, n_attempts=2
        ),
    }
    learner_model._states[DEMO_INTERMEDIATE_ID] = LearnerState(
        user_id=DEMO_INTERMEDIATE_ID,
        arm="static_personalized",
        mastery=inter_mastery,
        traits=inter_traits,
        affect=AffectiveState(engagement=0.90, frustration=0.10, fatigue=0.15),
        total_attempts=45,
    )

    # 3. Advanced (Grace Hopper)
    adv_traits = LearnerTraits(
        traits={
            "abstraction_preference": TraitEstimate(mean=0.88, variance=0.01, n_observations=25),
            "load_tolerance": TraitEstimate(mean=0.90, variance=0.01, n_observations=22),
            "depth_preference": TraitEstimate(mean=0.94, variance=0.01, n_observations=24),
            "persistence": TraitEstimate(mean=0.95, variance=0.01, n_observations=30),
            "self_efficacy": TraitEstimate(mean=0.92, variance=0.01, n_observations=25),
        }
    )
    adv_mastery = {}
    for c in get_all_concepts():
        adv_mastery[c.id] = ConceptMastery(concept_id=c.id, p_mastery=0.88, n_attempts=3)
    learner_model._states[DEMO_ADVANCED_ID] = LearnerState(
        user_id=DEMO_ADVANCED_ID,
        arm="generic",
        mastery=adv_mastery,
        traits=adv_traits,
        affect=AffectiveState(engagement=0.95, frustration=0.05, fatigue=0.05),
        total_attempts=90,
    )


# Singletons: real Explainer (M3), Telemetry Analyzer (M2), Curriculum Graph, and seeded demo model
_graph_service: GraphService = CurriculumGraphService()
_learner_model_service: LearnerModelService = FakeLearnerModel()
seed_demo_learner_states(_learner_model_service)
_planner_service: PlannerService = FakePlanner(_graph_service)  # type: ignore[arg-type]
_explainer_service: ExplainerService = GroundedExplainerService(_graph_service)
_feedback_analyzer: FeedbackAnalyzer = TelemetryFeedbackAnalyzer()


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
    """Reset service instances between tests to ensure test isolation."""
    global _graph_service, _learner_model_service, _planner_service
    global _explainer_service, _feedback_analyzer

    graph = CurriculumGraphService()
    learner_model = FakeLearnerModel()
    seed_demo_learner_states(learner_model)

    _graph_service = graph
    _learner_model_service = learner_model
    _planner_service = FakePlanner(graph)  # type: ignore[arg-type]
    _explainer_service = GroundedExplainerService(graph)
    _feedback_analyzer = TelemetryFeedbackAnalyzer()


# Typed Dependency Shortcuts for Route Handlers
GraphDep = Annotated[GraphService, Depends(get_graph_service)]
LearnerModelDep = Annotated[LearnerModelService, Depends(get_learner_model_service)]
PlannerDep = Annotated[PlannerService, Depends(get_planner_service)]
ExplainerDep = Annotated[ExplainerService, Depends(get_explainer_service)]
FeedbackAnalyzerDep = Annotated[FeedbackAnalyzer, Depends(get_feedback_analyzer)]
