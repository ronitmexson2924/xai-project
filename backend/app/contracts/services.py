"""Service interfaces between the two halves of the system.

The API layer (Mit) depends only on these Protocols. Real implementations live in the owner's
package; in-memory stand-ins live in `fakes.py` so either side can be developed first.
Changing this file requires a `contract` PR approved by both Ronit and Mit.
"""

from typing import Protocol
from uuid import UUID

from app.contracts.explanation import (
    Explanation,
    ExplanationEventIn,
    ExplanationFeedbackSummary,
    ExplanationRequest,
    StyleParams,
    StyleSource,
)
from app.contracts.graph import Concept, ConceptEdge, Item
from app.contracts.learner import AttemptRecord, LearnerState, StateDelta
from app.contracts.planning import Recommendation
from app.contracts.xai import BeliefExplanation, ChangeNotice, RecommendationWhy


class GraphService(Protocol):
    """Owner: Ronit (app/graph). Read-only access to concepts, edges and items."""

    def get_graph(self) -> tuple[list[Concept], list[ConceptEdge]]: ...

    def get_concept(self, concept_id: str) -> Concept: ...

    def prerequisites(self, concept_id: str) -> list[str]: ...

    def get_item(self, item_id: str) -> Item: ...

    def items_for_concept(self, concept_id: str, microcheck: bool = False) -> list[Item]: ...


class LearnerModelService(Protocol):
    """Owner: Ronit (app/learner_model). Module A + the update half of Module C.

    Every apply_* method is idempotent on its source id and returns what it changed.
    """

    def get_state(self, user_id: UUID) -> LearnerState: ...

    def init_from_questionnaire(self, user_id: UUID, answers: dict[str, int]) -> StateDelta: ...

    def apply_attempt(self, attempt: AttemptRecord) -> StateDelta: ...

    def apply_explanation_feedback(self, summary: ExplanationFeedbackSummary) -> StateDelta: ...


class PlannerService(Protocol):
    """Owner: Ronit (app/planner). Module D."""

    def next_step(self, state: LearnerState) -> Recommendation: ...

    def choose_style(
        self, state: LearnerState, concept_id: str
    ) -> tuple[StyleParams, StyleSource]: ...


class ExplainerService(Protocol):
    """Owner: Mit (app/explainer). Module B."""

    def explain(self, request: ExplanationRequest) -> Explanation: ...


class FeedbackAnalyzer(Protocol):
    """Owner: Mit (app/telemetry). The capture half of Module C."""

    def record_events(
        self, explanation_id: UUID, user_id: UUID, events: list[ExplanationEventIn]
    ) -> tuple[int, int]:
        """Store events; returns (accepted, duplicates)."""
        ...

    def summarize(self, explanation_id: UUID) -> ExplanationFeedbackSummary: ...


class ExplainabilityService(Protocol):
    """Owner: Ronit (app/planner/xai.py). Learner-facing explanations of the adaptation
    (docs/XAI_DESIGN.md). Rationales are stored when the planner decides, so `why` returns
    exactly the reasoning the decision was made with."""

    def why(self, recommendation_id: UUID) -> RecommendationWhy: ...

    def explain_belief(self, user_id: UUID, subject: str) -> BeliefExplanation: ...

    def explain_change(self, delta: StateDelta) -> ChangeNotice: ...
