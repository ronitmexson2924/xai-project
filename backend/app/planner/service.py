"""PlannerService implementation (Module D, docs/MODEL_SPEC.md §5).

`decide` applies the rules in priority order and returns a Trace (the rule that fired, evidence,
threshold). `next_step` turns it into a Recommendation and stores it together with its learner-
facing Rationale (docs/XAI_DESIGN.md), built from that same trace at decision time.
"""

import random
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from zlib import crc32

import numpy as np
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
from app.planner.policy import (
    DIAGNOSTIC_ATTEMPTS,
    DIAGNOSTIC_DEPTH_FRACTIONS,
    FRONTIER_PREREQ_MIN,
    MASTERED,
    POLICY_VERSION,
    PREREQ_WEAK,
    REVIEW_AFTER,
    REVIEW_EVERY,
    STRUGGLE_STREAK,
    SUSPICION_THRESHOLD,
    TARGET_P_CORRECT,
    Trace,
)
from app.planner.rationale import build_rationale
from app.planner.style import EPSILON_MIN, select_style


class Planner:
    def __init__(
        self,
        session: Session,
        graph: GraphSnapshot,
        learner_model: LearnerModel,
        seed: int = 0,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        epsilon: float = EPSILON_MIN,
    ) -> None:
        self.session = session
        self.graph = graph
        self.learner_model = learner_model
        self.seed = seed
        self.now = now
        self.epsilon = epsilon
        self._practice_concepts = graph.practice_concepts
        # user -> (latest recommendation id, its concept), for storing the style rationale
        self._last_recommendation: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}
        if not self._practice_concepts:
            raise LookupError("no approved practice items in the graph")

    # --- PlannerService --------------------------------------------------------------------------

    def next_step(self, state: LearnerState) -> Recommendation:
        mastery = self.learner_model.effective_mastery(state)
        activity = self.learner_model.activity(state.user_id)
        trace = self.decide(state, mastery, activity)
        item = self._pick_item(trace.concept_id, mastery[trace.concept_id], activity.recent_items)
        recommendation = Recommendation(
            id=uuid.uuid4(),
            user_id=state.user_id,
            kind=trace.kind,
            target_concept_id=trace.concept_id,
            item_id=item.id,
            reasons=trace.reasons,
            policy_version=POLICY_VERSION,
        )
        rationale = build_rationale(self, trace, state, activity, recommendation.id)
        self.session.add(
            m.RecommendationRow(
                id=recommendation.id,
                user_id=state.user_id,
                kind=trace.kind,
                target_concept_id=trace.concept_id,
                item_id=item.id,
                reasons=[r.model_dump(mode="json") for r in trace.reasons],
                policy_version=POLICY_VERSION,
                rationale=rationale.model_dump(mode="json"),
            )
        )
        self.session.flush()
        self._last_recommendation[state.user_id] = (recommendation.id, trace.concept_id)
        return recommendation

    def decide(
        self,
        state: LearnerState,
        mastery: dict[str, float],
        activity: Activity,
        skip: frozenset[str] = frozenset(),
    ) -> Trace:
        """The pure decision: no database writes, deterministic for a given state. Rules in
        `skip` are left out (used to find what would have been recommended otherwise)."""
        rng = random.Random(f"{self.seed}:{state.user_id}:{state.total_attempts}")
        rules = {
            "diagnostic": lambda: self._diagnostic(state, rng),
            "misconception": lambda: self._misconception(state, mastery),
            "prereq_gap": lambda: self._prerequisite_gap(mastery, activity),
            "review_turn": lambda: (
                self._review(mastery, activity, "review_turn") if self._review_turn(state) else None
            ),
            "frontier": lambda: self._frontier(state, mastery),
            "review": lambda: self._review(mastery, activity, "review"),
        }
        for name, rule in rules.items():
            if name not in skip and (trace := rule()) is not None:
                return trace
        return self._fallback(mastery)

    def choose_style(self, state: LearnerState, concept_id: str) -> tuple[StyleParams, StyleSource]:
        rng = np.random.default_rng(
            [
                self.seed,
                state.user_id.int & 0xFFFFFFFF,
                state.total_attempts,
                crc32(concept_id.encode()),
            ]
        )
        return select_style(
            arm=state.arm,
            traits=state.traits,
            affect=state.affect,
            posterior=self.learner_model.bandit_posterior(state.user_id),
            card_has_diagram=self.graph.get_concept(concept_id).card.diagram is not None,
            rng=rng,
            epsilon=self.epsilon,
        )

    # --- rules (each returns a Trace, or None if it does not apply) ------------------------------

    def _diagnostic(self, state: LearnerState, rng: random.Random) -> Trace | None:
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
        return Trace(
            "diagnostic",
            "diagnostic_item",
            concept_id,
            [reason],
            threshold=DIAGNOSTIC_ATTEMPTS,
            context={"done": state.total_attempts},
        )

    def _misconception(self, state: LearnerState, mastery: dict[str, float]) -> Trace | None:
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
        return Trace(
            "misconception",
            "remediate",
            target.concept_id,
            reasons,
            threshold=None if target.misconception_ids else SUSPICION_THRESHOLD,
            context={
                "misconception_ids": list(target.misconception_ids),
                "suspicion": target.misconception_suspicion,
            },
        )

    def _prerequisite_gap(self, mastery: dict[str, float], activity: Activity) -> Trace | None:
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
                return Trace(
                    "prereq_gap",
                    "remediate",
                    prereq,
                    [reason],
                    threshold=PREREQ_WEAK,
                    context={"struggling": concept_id},
                )
        return None

    def _frontier(self, state: LearnerState, mastery: dict[str, float]) -> Trace | None:
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
        return Trace("frontier", kind, concept_id, [reason], threshold=MASTERED)

    def _review_turn(self, state: LearnerState) -> bool:
        return state.total_attempts % REVIEW_EVERY == REVIEW_EVERY - 1

    def _review(self, mastery: dict[str, float], activity: Activity, rule: str) -> Trace | None:
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
        return Trace(
            rule,
            "review",
            concept_id,
            [reason],
            threshold=MASTERED,
            context={"last_practiced": activity.last_practiced[concept_id].isoformat()},
        )

    def _fallback(self, mastery: dict[str, float]) -> Trace:
        concept_id = min(self._practice_concepts, key=lambda c: (mastery[c], c))
        reason = ReasonEvidence(
            code=ReasonCode.REVIEW_DUE, concept_id=concept_id, value=mastery[concept_id]
        )
        return Trace("fallback", "review", concept_id, [reason])

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
