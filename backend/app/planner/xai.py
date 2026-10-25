"""ExplainabilityService implementation (docs/XAI_DESIGN.md): the single entry point Mit's API
uses for "Why this?" (E1-E3), "Why we think this" (E4) and change notices (E5)."""

from uuid import UUID

from app.contracts.learner import StateDelta
from app.contracts.xai import (
    BeliefExplanation,
    ChangeNotice,
    Rationale,
    RecommendationWhy,
    StyleRationale,
)
from app.db import models as m
from app.learner_model.explain import BeliefExplainer
from app.learner_model.service import LearnerModel


class Explainability:
    def __init__(self, learner_model: LearnerModel) -> None:
        self.session = learner_model.session
        self.beliefs = BeliefExplainer(learner_model)

    def why(self, recommendation_id: UUID) -> RecommendationWhy:
        """The rationale stored when the planner decided (never recomputed afterwards)."""
        row = self.session.get(m.RecommendationRow, recommendation_id)
        if row is None or row.rationale is None:
            raise LookupError(f"no rationale for recommendation {recommendation_id}")
        return RecommendationWhy(
            rationale=Rationale.model_validate(row.rationale),
            style=StyleRationale.model_validate(row.style_rationale)
            if row.style_rationale
            else None,
        )

    def explain_belief(self, user_id: UUID, subject: str) -> BeliefExplanation:
        return self.beliefs.explain_belief(user_id, subject)

    def explain_change(self, delta: StateDelta) -> ChangeNotice:
        return self.beliefs.explain_change(delta)
