"""Features for the performance model, rebuilt from the logs by replaying a learner's attempts.

The model predicts whether a learner answers a question correctly. Its inputs are what the system
knew *just before* that answer. Training rows and live predictions both come from `Replay`, so the
features a prediction is explained with are exactly the ones the model was trained on.

Mastery before each attempt is read from the attempt's own `state_updates` row (what the learner
model actually believed then), not recomputed. Unattempted concepts use the learner model's
prerequisite-informed prior, streaks and misconception flags follow the learner model's rules.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.graph import Item
from app.db import models as m
from app.graph.service import GraphSnapshot, is_test_item
from app.learner_model import bkt
from app.learner_model.service import MISCONCEPTION_CLEAR_STREAK

RECENT_WINDOW = 3  # attempts on the concept that "recent accuracy" looks at
MAX_ATTEMPTS = 50  # caps keep rare long histories from dominating the scale
MAX_DAYS = 30.0
NEVER_PRACTISED_DAYS = MAX_DAYS


@dataclass(frozen=True)
class Feature:
    name: str
    label: str  # what learners and the model card call it
    low: float  # plausible range: counterfactuals stay inside it
    high: float
    actionable: bool  # can the learner change it by practising? (counterfactuals vary only these)
    integer: bool = False


FEATURES: tuple[Feature, ...] = (
    Feature("mastery", "Estimated mastery of this concept", 0.0, 1.0, True),
    Feature("prereq_mean", "Mastery of its prerequisites (average)", 0.0, 1.0, True),
    Feature("prereq_min", "Weakest prerequisite", 0.0, 1.0, True),
    Feature("attempts", "Questions answered on this concept", 0, MAX_ATTEMPTS, True, True),
    Feature("recent_accuracy", "Recent accuracy on this concept", 0.0, 1.0, True),
    Feature("overall_accuracy", "Accuracy across all concepts", 0.0, 1.0, True),
    Feature("streak", "Current streak on this concept (+ right, - wrong)", -5, 5, True, True),
    Feature("misconception", "A known misconception is flagged", 0, 1, True, True),
    Feature("item_difficulty", "Difficulty of the question", 1, 5, False, True),
    Feature("guess_rate", "Chance of guessing it (1 / options)", 0.0, 1.0, False),
    Feature("days_since_practice", "Days since this concept was practised", 0.0, MAX_DAYS, True),
    Feature("self_efficacy", "Self-efficacy (questionnaire)", 0.0, 1.0, False),
    Feature("persistence", "Persistence (questionnaire)", 0.0, 1.0, False),
)
FEATURE_NAMES: tuple[str, ...] = tuple(f.name for f in FEATURES)
N_FEATURES = len(FEATURES)


@dataclass
class _Concept:
    attempts: int = 0
    recent: deque = field(default_factory=lambda: deque(maxlen=RECENT_WINDOW))
    streak: int = 0
    misconceptions: set[str] = field(default_factory=set)
    last_at: datetime | None = None


@dataclass
class Replay:
    """A learner's state as the logs say it was at some moment, advanced one attempt at a time."""

    graph: GraphSnapshot
    traits: dict[str, float]
    known: dict[str, float] = field(default_factory=dict)  # concept -> mastery after last attempt
    concepts: dict[str, _Concept] = field(default_factory=lambda: defaultdict(_Concept))
    correct: int = 0
    total: int = 0

    def features(self, item: Item, at: datetime, mastery: float | None = None) -> np.ndarray:
        """The feature vector for answering `item` at time `at`, before the answer is known."""
        effective = bkt.effective_mastery(self.graph, self.known)
        concept_id = item.concept_id
        prereqs = [effective[p] for p in self.graph.prerequisites(concept_id)]
        c = self.concepts[concept_id]
        recent = (sum(c.recent) + 1) / (len(c.recent) + 2)  # Laplace: 0.5 with no history
        days = (
            NEVER_PRACTISED_DAYS
            if c.last_at is None
            else min(MAX_DAYS, max(0.0, (at - c.last_at).total_seconds() / 86400))
        )
        values = {
            "mastery": effective[concept_id] if mastery is None else mastery,
            "prereq_mean": float(np.mean(prereqs)) if prereqs else 1.0,
            "prereq_min": min(prereqs) if prereqs else 1.0,
            "attempts": min(c.attempts, MAX_ATTEMPTS),
            "recent_accuracy": recent,
            "overall_accuracy": (self.correct + 1) / (self.total + 2),
            "streak": max(-5, min(5, c.streak)),
            "misconception": 1.0 if c.misconceptions else 0.0,
            "item_difficulty": item.difficulty,
            "guess_rate": bkt.guess_for(item),
            "days_since_practice": days,
            "self_efficacy": self.traits.get("self_efficacy", 0.5),
            "persistence": self.traits.get("persistence", 0.5),
        }
        return np.array([values[n] for n in FEATURE_NAMES], dtype=float)

    def advance(self, item: Item, response: str, correct: bool, at: datetime, after: float) -> None:
        """Apply one answered attempt, following the learner model's rules for streaks and flags."""
        c = self.concepts[item.concept_id]
        c.attempts += 1
        c.recent.append(1 if correct else 0)
        c.streak = max(c.streak, 0) + 1 if correct else min(c.streak, 0) - 1
        if not correct and response in item.distractor_misconceptions:
            c.misconceptions.add(item.distractor_misconceptions[response])
        elif correct and c.streak >= MISCONCEPTION_CLEAR_STREAK:
            c.misconceptions.clear()
        c.last_at = at
        self.known[item.concept_id] = after
        self.correct += int(correct)
        self.total += 1


@dataclass(frozen=True)
class Row:
    user_id: UUID
    attempt_id: UUID
    x: np.ndarray
    y: int
    bkt_p_correct: float  # BKT's own prediction for the same answer: the baseline to beat


def _questionnaire_traits(session: Session, user_id: UUID) -> dict[str, float]:
    delta = session.scalar(
        select(m.StateUpdateRow.delta).where(
            m.StateUpdateRow.user_id == user_id, m.StateUpdateRow.source == "questionnaire"
        )
    )
    changes = (delta or {}).get("trait_changes", {})
    return {trait: float(after) for trait, (_before, after) in changes.items()}


def replay(
    session: Session, graph: GraphSnapshot, user_id: UUID, until: datetime | None = None
) -> tuple[Replay, list[Row]]:
    """Replay a learner's practice attempts (oldest first, optionally only those before `until`).
    Returns the state afterwards and one training row per attempt."""
    attempts = session.execute(
        select(m.AttemptRow)
        .where(m.AttemptRow.user_id == user_id)
        .order_by(m.AttemptRow.created_at, m.AttemptRow.id)
    ).scalars()
    before_after = {
        row.source_id: row.delta.get("mastery_changes", {})
        for row in session.scalars(
            select(m.StateUpdateRow).where(
                m.StateUpdateRow.user_id == user_id, m.StateUpdateRow.source == "attempt"
            )
        )
    }
    state = Replay(graph=graph, traits=_questionnaire_traits(session, user_id))
    rows: list[Row] = []
    for attempt in attempts:
        if until is not None and attempt.created_at >= until:
            break
        if is_test_item(attempt.item_id):
            continue  # pre/post-tests do not update the learner model
        try:
            item = graph.get_item(attempt.item_id)
        except KeyError:
            continue  # item withdrawn from the bank since
        change = before_after.get(str(attempt.id), {}).get(item.concept_id)
        if change is None:
            continue  # never applied to the learner model: nothing to learn from
        before, after = change
        x = state.features(item, attempt.created_at, mastery=before)
        p_bkt = bkt.predict_correct(before, bkt.DEFAULT_PARAMS.p_slip, bkt.guess_for(item))
        rows.append(Row(user_id, attempt.id, x, int(attempt.correct), p_bkt))
        state.advance(item, attempt.response, attempt.correct, attempt.created_at, after)
    return state, rows


def dataset(
    session: Session, graph: GraphSnapshot, user_ids: list[UUID]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Training data for these learners: X, y, BKT's predictions, and each row's learner index
    (for splitting by learner, so no learner is in both training and test data)."""
    xs, ys, bkts, groups = [], [], [], []
    for index, user_id in enumerate(user_ids):
        for row in replay(session, graph, user_id)[1]:
            xs.append(row.x)
            ys.append(row.y)
            bkts.append(row.bkt_p_correct)
            groups.append(index)
    if not xs:
        return np.empty((0, N_FEATURES)), np.empty(0), np.empty(0), np.empty(0)
    return np.array(xs), np.array(ys), np.array(bkts), np.array(groups)
