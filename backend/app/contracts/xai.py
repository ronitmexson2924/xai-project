"""Learner-facing explanations of the adaptation itself (docs/XAI_DESIGN.md).

Ronit's planner/learner model produce these; Mit's API serves them and his UI renders them.
Every text field is plain language for the learner; every number comes from the model state the
decision was actually made on (faithfulness rules, XAI_DESIGN §3).
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.contracts.explanation import StyleSource
from app.contracts.learner import StateUpdateSource
from app.contracts.reasons import ReasonCode, ReasonEvidence

Confidence = Literal["tentative", "moderate", "confident"]

CounterfactualKind = Literal[
    "mastery_at_least",  # the concept's mastery reaches target_value
    "misconception_cleared",  # the flagged misconception is cleared (2 correct in a row)
    "suspicion_below",  # misconception suspicion falls below target_value
    "placement_complete",  # the placement (diagnostic) questions are finished
    "review_done",  # the due review has been practised
]


class Counterfactual(BaseModel):
    """E2: what would change the decision. Only produced if re-running the planner on the
    changed situation really gives a different recommendation."""

    kind: CounterfactualKind
    concept_id: str
    target_value: float | None = None
    steps_needed: int | None = None  # e.g. correct answers needed (BKT forward simulation)
    condition: str  # "answer about 2 more questions on Recursion: base case correctly"
    outcome: str  # "you would move on to Recursion: recursive case"
    outcome_concept_id: str  # what the planner recommends in the changed situation


class Rationale(BaseModel):
    """E1 + E2 for one recommendation, built from the planner's decision trace."""

    recommendation_id: UUID
    rule: ReasonCode
    summary: str
    evidence: list[ReasonEvidence]
    threshold: float | None = None  # the threshold the rule compared against, if any
    alternative: str | None = None  # what would have been recommended without this rule
    counterfactuals: list[Counterfactual] = []


class StyleRationale(BaseModel):
    """E3: why the explanation is written the way it is."""

    source: StyleSource
    summary: str
    p_best: float | None = Field(default=None, ge=0.0, le=1.0)  # posterior P(style is best)
    confidence: Confidence


class RecommendationWhy(BaseModel):
    """Response of GET /recommendations/{id}/why."""

    rationale: Rationale
    style: StyleRationale | None = None  # None until a style was chosen for the recommendation


class BeliefExplanation(BaseModel):
    """E4: why the system believes something about the learner (open learner model)."""

    subject: str  # a concept id or a trait name
    label: str  # concept name or plain-language trait name
    value: float = Field(ge=0.0, le=1.0)
    confidence: Confidence
    summary: str
    top_evidence: list[str] = []  # the events that moved this belief most, newest first


class ChangeNotice(BaseModel):
    """E5: what one update (answer, explanation feedback, questionnaire) changed."""

    source: StateUpdateSource
    messages: list[str] = []
