"""In-memory stand-ins for every service in `services.py`.

They exist so Mit can build the API/UI before Ronit's models are merged (and vice versa).
They are deliberately naive: no BKT, no bandit, no LLM. Never use them in production wiring.
"""

from datetime import datetime
from uuid import UUID, uuid4

from app.contracts.explanation import (
    Explanation,
    ExplanationEventIn,
    ExplanationFeedbackSummary,
    ExplanationRequest,
    StyleParams,
    StyleSource,
)
from app.contracts.graph import Concept, ConceptCard, ConceptEdge, Item
from app.contracts.learner import (
    TRAIT_NAMES,
    AttemptRecord,
    ConceptMastery,
    ExperimentArm,
    LearnerState,
    LearnerTraits,
    StateDelta,
    TraitEstimate,
)
from app.contracts.planning import Recommendation
from app.contracts.reasons import ReasonCode, ReasonEvidence
from app.contracts.xai import (
    BeliefExplanation,
    ChangeNotice,
    Rationale,
    RecommendationWhy,
    StyleRationale,
)

_CONCEPTS = [
    Concept(
        id="loops",
        name="Loops",
        cluster="basics",
        description="Repeating a block of code.",
        difficulty=1,
        card=ConceptCard(
            definition="A loop runs a block of code repeatedly while a condition holds.",
            key_idea="Every loop needs a condition that eventually becomes false.",
            worked_example="for i in range(3): print(i)  # prints 0, 1, 2",
            pitfall="Off-by-one: range(3) stops before 3.",
        ),
    ),
    Concept(
        id="recursion-base-case",
        name="Recursion: base case",
        cluster="recursion",
        description="The stopping condition of a recursive function.",
        difficulty=2,
        card=ConceptCard(
            definition="A base case is an input a recursive function answers without recursing.",
            key_idea="Each recursive call must move closer to a base case.",
            worked_example="def fact(n): return 1 if n == 0 else n * fact(n - 1)",
            pitfall="A missing or unreachable base case causes infinite recursion.",
        ),
    ),
]
_EDGES = [ConceptEdge(src="loops", dst="recursion-base-case")]
_ITEMS = [
    Item(
        id="loops-1",
        concept_id="loops",
        kind="mcq",
        stem="How many times does `for i in range(3)` run its body?",
        options=["2", "3", "4"],
        answer="3",
        distractor_misconceptions={"4": "loops-off-by-one"},
    ),
    Item(
        id="rbc-1",
        concept_id="recursion-base-case",
        kind="mcq",
        stem="What does fact(0) return for `fact(n) = 1 if n == 0 else n * fact(n-1)`?",
        options=["0", "1", "It never returns"],
        answer="1",
        is_microcheck=True,
    ),
]


class FakeGraph:
    def get_graph(self) -> tuple[list[Concept], list[ConceptEdge]]:
        return list(_CONCEPTS), list(_EDGES)

    def get_concept(self, concept_id: str) -> Concept:
        return next(c for c in _CONCEPTS if c.id == concept_id)

    def prerequisites(self, concept_id: str) -> list[str]:
        return [e.src for e in _EDGES if e.dst == concept_id]

    def get_item(self, item_id: str) -> Item:
        return next(i for i in _ITEMS if i.id == item_id)

    def items_for_concept(self, concept_id: str, microcheck: bool = False) -> list[Item]:
        return [i for i in _ITEMS if i.concept_id == concept_id and i.is_microcheck == microcheck]


def _neutral_traits() -> LearnerTraits:
    return LearnerTraits(traits={t: TraitEstimate(mean=0.5, variance=0.04) for t in TRAIT_NAMES})


class FakeLearnerModel:
    def __init__(self, arm: ExperimentArm = "closed_loop") -> None:
        self.arm = arm
        self._states: dict[UUID, LearnerState] = {}
        self._applied: set[str] = set()

    def get_state(self, user_id: UUID) -> LearnerState:
        if user_id not in self._states:
            self._states[user_id] = LearnerState(
                user_id=user_id, arm=self.arm, mastery={}, traits=_neutral_traits()
            )
        return self._states[user_id]

    def init_from_questionnaire(self, user_id: UUID, answers: dict[str, int]) -> StateDelta:
        self.get_state(user_id)
        return StateDelta(user_id=user_id, source="questionnaire", source_id=str(user_id))

    def apply_attempt(self, attempt: AttemptRecord) -> StateDelta:
        delta = StateDelta(user_id=attempt.user_id, source="attempt", source_id=str(attempt.id))
        if delta.source_id in self._applied:
            return delta
        self._applied.add(delta.source_id)
        state = self.get_state(attempt.user_id)
        m = state.mastery.setdefault(
            attempt.concept_id, ConceptMastery(concept_id=attempt.concept_id, p_mastery=0.2)
        )
        before = m.p_mastery
        m.p_mastery = min(1.0, max(0.0, before + (0.1 if attempt.correct else -0.1)))
        m.n_attempts += 1
        state.total_attempts += 1
        delta.mastery_changes[attempt.concept_id] = (before, m.p_mastery)
        return delta

    def apply_explanation_feedback(self, summary: ExplanationFeedbackSummary) -> StateDelta:
        delta = StateDelta(
            user_id=summary.user_id,
            source="explanation_feedback",
            source_id=str(summary.explanation_id),
        )
        if delta.source_id in self._applied:
            return delta
        self._applied.add(delta.source_id)
        if summary.clarity_rating is not None and self.arm == "closed_loop":
            trait = self.get_state(summary.user_id).traits.traits["abstraction_preference"]
            before = trait.mean
            nudge = 0.02 if summary.style.example_first else -0.02
            sign = 1 if summary.clarity_rating < 3 else -1
            trait.mean = min(1.0, max(0.0, before + sign * nudge))
            trait.n_observations += 1
            delta.trait_changes["abstraction_preference"] = (before, trait.mean)
        return delta


class FakePlanner:
    def __init__(self, graph: FakeGraph | None = None) -> None:
        self.graph = graph or FakeGraph()

    def next_step(self, state: LearnerState) -> Recommendation:
        concepts, _ = self.graph.get_graph()
        target = min(
            concepts,
            key=lambda c: state.mastery[c.id].p_mastery if c.id in state.mastery else 0.2,
        )
        items = self.graph.items_for_concept(target.id) or self.graph.items_for_concept(
            target.id, microcheck=True
        )
        return Recommendation(
            id=uuid4(),
            user_id=state.user_id,
            kind="practice_item",
            target_concept_id=target.id,
            item_id=items[0].id if items else None,
            reasons=[ReasonEvidence(code=ReasonCode.READY_FOR_NEXT, concept_id=target.id)],
            policy_version="fake-0",
        )

    def choose_style(self, state: LearnerState, concept_id: str) -> tuple[StyleParams, StyleSource]:
        return StyleParams(example_first=True, length="medium", depth="how"), "generic"


class FakeExplainer:
    def __init__(self, graph: FakeGraph | None = None) -> None:
        self.graph = graph or FakeGraph()

    def explain(self, request: ExplanationRequest) -> Explanation:
        card = self.graph.get_concept(request.concept_ids[0]).card
        parts = (
            [card.worked_example, card.key_idea]
            if request.style.example_first
            else [
                card.key_idea,
                card.worked_example,
            ]
        )
        return Explanation(
            id=uuid4(),
            recommendation_id=request.recommendation_id,
            user_id=request.user_id,
            concept_ids=request.concept_ids,
            style=request.style,
            style_source=request.style_source,
            body_markdown="\n\n".join([card.definition, *parts]),
            source="template",
            prompt_version="fake-0",
            followup_item_id=request.followup_item_id,
        )


class FakeFeedbackAnalyzer:
    """Effective dwell = sum of shown/visible -> hidden/dismissed intervals."""

    def __init__(self) -> None:
        self._explanations: dict[UUID, Explanation] = {}
        self._events: dict[UUID, list[ExplanationEventIn]] = {}
        self._seen_keys: set[UUID] = set()

    def register(self, explanation: Explanation) -> None:
        """Fake-only: the real analyzer reads explanation metadata from the database."""
        self._explanations[explanation.id] = explanation

    def record_events(
        self, explanation_id: UUID, user_id: UUID, events: list[ExplanationEventIn]
    ) -> tuple[int, int]:
        accepted = duplicates = 0
        for event in events:
            if event.idempotency_key in self._seen_keys:
                duplicates += 1
                continue
            self._seen_keys.add(event.idempotency_key)
            self._events.setdefault(explanation_id, []).append(event)
            accepted += 1
        return accepted, duplicates

    def summarize(self, explanation_id: UUID) -> ExplanationFeedbackSummary:
        exp = self._explanations[explanation_id]
        events = sorted(self._events.get(explanation_id, []), key=lambda e: e.client_ts)
        dwell_ms = 0
        visible_since: datetime | None = None
        clarity: int | None = None
        followup: bool | None = None
        for e in events:
            if e.type in ("shown", "visible") and visible_since is None:
                visible_since = e.client_ts
            elif e.type in ("hidden", "dismissed") and visible_since is not None:
                dwell_ms += int((e.client_ts - visible_since).total_seconds() * 1000)
                visible_since = None
            elif e.type == "clarity_rated":
                clarity = int(e.payload["rating"])
            elif e.type == "followup_answered":
                followup = bool(e.payload["correct"])
        types = {e.type for e in events}
        return ExplanationFeedbackSummary(
            explanation_id=exp.id,
            user_id=exp.user_id,
            concept_ids=exp.concept_ids,
            style=exp.style,
            style_source=exp.style_source,
            effective_dwell_ms=dwell_ms,
            expanded="expanded" in types,
            replays=sum(1 for e in events if e.type == "replayed"),
            clarity_rating=clarity,
            followup_correct=followup,
            dismissed_quickly=dwell_ms < 3000 and types <= {"shown", "hidden", "dismissed"},
        )


class FakeExplainability:
    """Fixed, plausible explanations so the "Why this?" UI can be built before R9/R10 merge."""

    def why(self, recommendation_id: UUID) -> RecommendationWhy:
        return RecommendationWhy(
            rationale=Rationale(
                recommendation_id=recommendation_id,
                rule=ReasonCode.READY_FOR_NEXT,
                summary="You know the topics this one builds on, so it is the next step.",
                evidence=[ReasonEvidence(code=ReasonCode.READY_FOR_NEXT, concept_id="loops")],
            ),
            style=StyleRationale(
                source="generic",
                summary="This is the app's standard explanation style.",
                confidence="tentative",
            ),
        )

    def explain_belief(self, user_id: UUID, subject: str) -> BeliefExplanation:
        return BeliefExplanation(
            subject=subject,
            label=subject,
            value=0.5,
            confidence="tentative",
            summary="We don't have enough of your answers yet to say much.",
        )

    def explain_change(self, delta: StateDelta) -> ChangeNotice:
        return ChangeNotice(source=delta.source, messages=[])
