"""PlannerService implementation (Module D, docs/MODEL_SPEC.md §5).

next_step applies the rules in priority order and returns a Recommendation whose ReasonEvidence
explains the decision; the recommendation is stored so explanations and attempts can reference it.
"""

import random
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.contracts.explanation import StyleParams, StyleSource
from app.contracts.graph import Item
from app.contracts.learner import LearnerState
from app.contracts.planning import Recommendation, RecommendationKind
from app.contracts.reasons import ReasonCode, ReasonEvidence
from app.db import models as m
from app.graph.service import GraphSnapshot
from app.learner_model import bkt
from app.learner_model.service import Activity, LearnerModel

POLICY_VERSION = "planner-v1"

DIAGNOSTIC_ATTEMPTS = 8
DIAGNOSTIC_DEPTH_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 0.1, 0.35, 0.6, 0.85)
SUSPICION_THRESHOLD = 0.5
STRUGGLE_STREAK = -2  # two wrong in a row
PREREQ_WEAK = 0.6
FRONTIER_PREREQ_MIN = 0.85
MASTERED = 0.95
REVIEW_AFTER = timedelta(hours=48)
REVIEW_EVERY = 6  # when a review is due, every 6th step is a review
TARGET_P_CORRECT = 0.7

# (kind, target concept, reasons) produced by one planner rule
Decision = tuple[RecommendationKind, str, list[ReasonEvidence]]


class Planner:
    def __init__(
        self,
        session: Session,
        graph: GraphSnapshot,
        learner_model: LearnerModel,
        seed: int = 0,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.session = session
        self.graph = graph
        self.learner_model = learner_model
        self.seed = seed
        self.now = now
        self._practice_concepts = {
            c for c in graph.concept_ids if graph.items_for_concept(c, microcheck=False)
        }
        if not self._practice_concepts:
            raise LookupError("no approved practice items in the graph")

    # --- PlannerService --------------------------------------------------------------------------

    def next_step(self, state: LearnerState) -> Recommendation:
        mastery = self.learner_model.effective_mastery(state)
        activity = self.learner_model.activity(state.user_id)
        rng = random.Random(f"{self.seed}:{state.user_id}:{state.total_attempts}")

        decision = (
            self._diagnostic(state, rng)
            or self._misconception(state, mastery)
            or self._prerequisite_gap(mastery, activity)
            or (self._review(mastery, activity) if self._review_turn(state) else None)
            or self._frontier(state, mastery)
            or self._review(mastery, activity)
            or self._fallback(mastery)
        )
        kind, concept_id, reasons = decision
        item = self._pick_item(concept_id, mastery[concept_id], activity.recent_items)
        recommendation = Recommendation(
            id=uuid.uuid4(),
            user_id=state.user_id,
            kind=kind,
            target_concept_id=concept_id,
            item_id=item.id,
            reasons=reasons,
            policy_version=POLICY_VERSION,
        )
        self.session.add(
            m.RecommendationRow(
                id=recommendation.id,
                user_id=state.user_id,
                kind=kind,
                target_concept_id=concept_id,
                item_id=item.id,
                reasons=[r.model_dump(mode="json") for r in reasons],
                policy_version=POLICY_VERSION,
            )
        )
        self.session.flush()
        return recommendation

    def choose_style(self, state: LearnerState, concept_id: str) -> tuple[StyleParams, StyleSource]:
        raise NotImplementedError("task R5")

    # --- rules (each returns (kind, concept_id, reasons) or None) --------------------------------

    def _diagnostic(self, state: LearnerState, rng: random.Random) -> Decision | None:
        if state.total_attempts >= DIAGNOSTIC_ATTEMPTS:
            return None
        depth = self.graph.depth
        max_depth = max(depth.values())
        fraction = DIAGNOSTIC_DEPTH_FRACTIONS[
            state.total_attempts % len(DIAGNOSTIC_DEPTH_FRACTIONS)
        ]
        target = round(fraction * max_depth)
        candidates = sorted(c for c in self._practice_concepts if c not in state.mastery)
        if not candidates:
            return None
        best = min(abs(depth[c] - target) for c in candidates)
        concept_id = rng.choice([c for c in candidates if abs(depth[c] - target) == best])
        reason = ReasonEvidence(
            code=ReasonCode.DIAGNOSTIC,
            concept_id=concept_id,
            detail=f"placement question {state.total_attempts + 1} of {DIAGNOSTIC_ATTEMPTS}",
        )
        return "diagnostic_item", concept_id, [reason]

    def _misconception(self, state: LearnerState, mastery: dict[str, float]) -> Decision | None:
        flagged = [
            c
            for c in state.mastery.values()
            if c.concept_id in self._practice_concepts
            and (c.misconception_ids or c.misconception_suspicion >= SUSPICION_THRESHOLD)
        ]
        if not flagged:
            return None
        target = min(flagged, key=lambda c: (mastery[c.concept_id], c.concept_id))
        if target.misconception_ids:
            reasons = [
                ReasonEvidence(
                    code=ReasonCode.MISCONCEPTION_DETECTED,
                    concept_id=target.concept_id,
                    value=mastery[target.concept_id],
                    detail=self.graph.misconception(mid).description,
                )
                for mid in target.misconception_ids
            ]
        else:
            reasons = [
                ReasonEvidence(
                    code=ReasonCode.MISCONCEPTION_SUSPECTED,
                    concept_id=target.concept_id,
                    value=target.misconception_suspicion,
                    detail="recent explanations did not seem to land",
                )
            ]
        return "remediate", target.concept_id, reasons

    def _prerequisite_gap(self, mastery: dict[str, float], activity: Activity) -> Decision | None:
        struggling = [c for c, s in activity.streaks.items() if s <= STRUGGLE_STREAK]
        for concept_id in sorted(
            struggling, key=lambda c: activity.last_practiced[c], reverse=True
        ):
            weak = [
                p
                for p in self.graph.prerequisites(concept_id)
                if mastery[p] < PREREQ_WEAK and p in self._practice_concepts
            ]
            if weak:
                prereq = min(weak, key=lambda p: (mastery[p], p))
                reason = ReasonEvidence(
                    code=ReasonCode.PREREQ_GAP,
                    concept_id=prereq,
                    value=mastery[prereq],
                    detail=f"needed for {self.graph.get_concept(concept_id).name}",
                )
                return "remediate", prereq, [reason]
        return None

    def _frontier(self, state: LearnerState, mastery: dict[str, float]) -> Decision | None:
        frontier = [
            c
            for c in self.graph.topological_order
            if c in self._practice_concepts
            and mastery[c] < MASTERED
            and all(mastery[p] >= FRONTIER_PREREQ_MIN for p in self.graph.prerequisites(c))
        ]
        if not frontier:
            return None
        in_progress = [c for c in frontier if c in state.mastery]
        if in_progress:
            concept_id = min(in_progress, key=lambda c: (mastery[c], c))
            kind: RecommendationKind = "practice_item"
        else:
            concept_id, kind = frontier[0], "advance"
        reason = ReasonEvidence(
            code=ReasonCode.READY_FOR_NEXT, concept_id=concept_id, value=mastery[concept_id]
        )
        return kind, concept_id, [reason]

    def _review_turn(self, state: LearnerState) -> bool:
        return state.total_attempts % REVIEW_EVERY == REVIEW_EVERY - 1

    def _review(self, mastery: dict[str, float], activity: Activity) -> Decision | None:
        cutoff = self.now() - REVIEW_AFTER
        due = [
            c
            for c, when in activity.last_practiced.items()
            if c in self._practice_concepts and mastery[c] >= MASTERED and when < cutoff
        ]
        if not due:
            return None
        concept_id = min(due, key=lambda c: (activity.last_practiced[c], c))
        reason = ReasonEvidence(
            code=ReasonCode.REVIEW_DUE,
            concept_id=concept_id,
            value=mastery[concept_id],
            detail=f"last practised {activity.last_practiced[concept_id]:%Y-%m-%d}",
        )
        return "review", concept_id, [reason]

    def _fallback(self, mastery: dict[str, float]) -> Decision:
        concept_id = min(self._practice_concepts, key=lambda c: (mastery[c], c))
        reason = ReasonEvidence(
            code=ReasonCode.REVIEW_DUE, concept_id=concept_id, value=mastery[concept_id]
        )
        return "review", concept_id, [reason]

    # --- item choice ------------------------------------------------------------------------------

    def _pick_item(self, concept_id: str, mastery: float, recent: list[str]) -> Item:
        """The item whose predicted P(correct) is closest to TARGET_P_CORRECT, avoiding recent
        items; harder items are preferred as mastery grows."""
        items = self.graph.items_for_concept(concept_id, microcheck=False)
        fresh = [i for i in items if i.id not in recent] or items
        target_difficulty = 1 + round(4 * mastery)

        def cost(item: Item) -> tuple[float, str]:
            p = bkt.predict_correct(mastery, self.learner_model.params.p_slip, bkt.guess_for(item))
            return abs(p - TARGET_P_CORRECT) + 0.05 * abs(
                item.difficulty - target_difficulty
            ), item.id

        return min(fresh, key=cost)
