"""Faithful learner-facing rationales for planner decisions (XAI E1 + E2, docs/XAI_DESIGN.md).

Built only from the planner's Trace, at decision time. Counterfactuals are computed by changing
the learner state as the counterfactual says (e.g. BKT-simulating n correct answers), re-running
the planner's own `decide`, and keeping the counterfactual only if the decision really changes.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING

from app.contracts.learner import ConceptMastery, LearnerState
from app.contracts.reasons import ReasonCode
from app.contracts.xai import Counterfactual, CounterfactualKind, Rationale
from app.learner_model import bkt
from app.learner_model.service import MISCONCEPTION_CLEAR_STREAK, Activity
from app.learner_model.updates import SUSPICION_DECAY
from app.planner.policy import (
    DIAGNOSTIC_ATTEMPTS,
    MASTERED,
    PREREQ_WEAK,
    SUSPICION_THRESHOLD,
    Trace,
)

if TYPE_CHECKING:
    from app.planner.service import Planner

MAX_STEPS = 20  # beyond this many answers we say "once you have mastered it" instead of a number

RULE_CODE = {
    "diagnostic": ReasonCode.DIAGNOSTIC,
    "prereq_gap": ReasonCode.PREREQ_GAP,
    "review_turn": ReasonCode.REVIEW_DUE,
    "frontier": ReasonCode.READY_FOR_NEXT,
    "review": ReasonCode.REVIEW_DUE,
    "fallback": ReasonCode.REVIEW_DUE,
}

# Labels about the learner that explanations must never use (XAI_DESIGN §3, rule 5).
BANNED_PHRASES = (
    "learning style",
    "visual learner",
    "auditory learner",
    "kinesthetic",
    "you are a ",
    "lazy",
    "slow learner",
    "weak student",
    "not persistent",
    "low persistence",
    "low self-efficacy",
    "personality",
)


def pct(x: float) -> str:
    return f"{round(100 * x)}%"


def correct_answers_needed(
    mastery: float, target: float, params: bkt.BKTParams, guess: float
) -> tuple[int, float] | None:
    """How many correct answers in a row take BKT mastery from `mastery` to >= target, and the
    mastery reached; None if it takes more than MAX_STEPS."""
    value = mastery
    for steps in range(1, MAX_STEPS + 1):
        value = bkt.update(value, True, params.p_slip, guess, params.p_learn)
        if value >= target:
            return steps, value
    return None


def _answered(state: LearnerState, concept_id: str, mastery: float, steps: int, **changes):
    """A copy of the state after `steps` more answers on one concept, with that concept's
    mastery set to `mastery` and any other ConceptMastery fields changed."""
    new = state.model_copy(deep=True)
    current = new.mastery.get(concept_id) or ConceptMastery(concept_id=concept_id, p_mastery=0)
    new.mastery[concept_id] = current.model_copy(
        update={"p_mastery": mastery, "n_attempts": current.n_attempts + steps, **changes}
    )
    new.total_attempts += steps
    return new


class _Builder:
    def __init__(self, planner: Planner, trace: Trace, state: LearnerState, activity: Activity):
        self.planner, self.trace, self.state, self.activity = planner, trace, state, activity
        self.graph = planner.graph
        self.params = planner.learner_model.params
        self.mastery = planner.learner_model.effective_mastery(state)

    def name(self, concept_id: str) -> str:
        return self.graph.get_concept(concept_id).name

    def guess(self, concept_id: str) -> float:
        items = self.graph.items_for_concept(concept_id) or self.graph.items_for_concept(
            concept_id, microcheck=True
        )
        if not items:
            return self.params.p_guess
        return sum(bkt.guess_for(i, self.params) for i in items) / len(items)

    def rerun(self, state: LearnerState, activity: Activity | None = None) -> Trace:
        return self.planner.decide(
            state, self.planner.learner_model.effective_mastery(state), activity or self.activity
        )

    def outcome_text(self, t: Trace) -> str:
        name = self.name(t.concept_id)
        return {
            "diagnostic": f"the placement questions would continue with {name}",
            "misconception": f"we would next work on a misunderstanding in {name}",
            "prereq_gap": f"we would first practise {name}",
            "review_turn": f"you would review {name}",
            "review": f"you would review {name}",
            "fallback": f"we would reinforce {name}",
            "frontier": (
                f"you would move on to {name}"
                if t.kind == "advance"
                else f"you would continue with {name}"
            ),
        }[t.rule]

    # --- E1 -------------------------------------------------------------------------------------

    def summary(self) -> str:
        t, c = self.trace, self.trace.concept_id
        name, m = self.name(c), self.mastery[c]
        if t.rule == "diagnostic":
            return (
                f"This is placement question {t.context['done'] + 1} of {DIAGNOSTIC_ATTEMPTS}. "
                "We're checking what you already know, so you don't have to repeat what you've "
                "mastered."
            )
        if t.rule == "misconception" and t.context["misconception_ids"]:
            mistake = self.graph.misconception(t.context["misconception_ids"][0]).description
            return (
                f'One of your recent answers on {name} matches a common mistake: "{mistake}" '
                "We're sorting that out before moving on."
            )
        if t.rule == "misconception":
            return (
                f"The last explanations of {name} didn't seem to land (judging by your follow-up "
                "answers and ratings), so we're coming back to it."
            )
        if t.rule == "prereq_gap":
            struggling = self.name(t.context["struggling"])
            return (
                f"You got two questions in a row wrong on {struggling}. That often means a "
                f"building block is shaky: your estimated mastery of {name} is {pct(m)}, below the "
                f"{pct(PREREQ_WEAK)} we look for, so we're practising it first."
            )
        if t.rule in ("review", "review_turn"):
            when = datetime.fromisoformat(t.context["last_practiced"]).strftime("%d %b")
            return (
                f"You mastered {name} (last practised {when}). A short review now helps you keep "
                "it."
            )
        if t.rule == "fallback":
            return (
                f"Nothing on your path needs new work right now, so we're reinforcing {name}, "
                f"your least secure topic ({pct(m)})."
            )
        if t.kind == "advance":
            prereqs = [self.name(p) for p in self.graph.prerequisites(c)]
            if not prereqs:
                return f"{name} is a starting topic, so it's a good next step."
            listed = ", ".join(prereqs[:3]) + (" and more" if len(prereqs) > 3 else "")
            return f"You know what {name} builds on ({listed}), so it's your next step."
        return (
            f"You're working on {name} (estimated mastery {pct(m)}). We keep practising until it "
            f"reaches {pct(MASTERED)}."
        )

    def alternative(self) -> str | None:
        t = self.trace
        if t.rule in ("diagnostic", "frontier", "fallback"):
            return None  # only rules that interrupt the normal path have a meaningful "otherwise"
        skip = {t.rule} | (
            {"review", "review_turn"} if t.rule in ("review", "review_turn") else set()
        )
        alt = self.planner.decide(self.state, self.mastery, self.activity, frozenset(skip))
        if alt.concept_id == t.concept_id:
            return None
        return f"Without this, {self.outcome_text(alt)}."

    # --- E2 -------------------------------------------------------------------------------------

    def candidates(
        self,
    ) -> list[
        tuple[CounterfactualKind, float | None, int | None, str, LearnerState, Activity | None]
    ]:
        t, c = self.trace, self.trace.concept_id
        name, m = self.name(c), self.mastery[c]
        out = []
        if t.rule == "diagnostic":
            remaining = DIAGNOSTIC_ATTEMPTS - t.context["done"]
            state = self.state.model_copy(update={"total_attempts": DIAGNOSTIC_ATTEMPTS})
            plural = "s" if remaining != 1 else ""
            out.append(
                (
                    "placement_complete",
                    None,
                    remaining,
                    f"after the remaining {remaining} placement question{plural} "
                    "(based on your answers so far)",
                    state,
                    None,
                )
            )
        elif t.rule == "misconception" and t.context["misconception_ids"]:
            steps = MISCONCEPTION_CLEAR_STREAK
            value = m
            for _ in range(steps):
                value = bkt.update(
                    value, True, self.params.p_slip, self.guess(c), self.params.p_learn
                )
            state = _answered(self.state, c, value, steps, misconception_ids=[])
            out.append(
                (
                    "misconception_cleared",
                    None,
                    steps,
                    f"answer {steps} questions on {name} correctly in a row",
                    state,
                    None,
                )
            )
        elif t.rule == "misconception":
            suspicion, steps, value = t.context["suspicion"], 0, m
            while suspicion >= SUSPICION_THRESHOLD and steps < MAX_STEPS:
                suspicion *= SUSPICION_DECAY
                value = bkt.update(
                    value, True, self.params.p_slip, self.guess(c), self.params.p_learn
                )
                steps += 1
            state = _answered(self.state, c, value, steps, misconception_suspicion=suspicion)
            out.append(
                (
                    "suspicion_below",
                    SUSPICION_THRESHOLD,
                    steps,
                    f"answer {steps} follow-up question{'s' if steps != 1 else ''} on {name} "
                    "correctly",
                    state,
                    None,
                )
            )
        elif t.rule in ("prereq_gap", "frontier"):
            target = PREREQ_WEAK if t.rule == "prereq_gap" else MASTERED
            needed = correct_answers_needed(m, target, self.params, self.guess(c))
            if needed is not None:
                steps, value = needed
                state = _answered(self.state, c, value, steps)
                out.append(
                    (
                        "mastery_at_least",
                        target,
                        steps,
                        f"answer about {steps} more question{'s' if steps != 1 else ''} on {name} "
                        f"correctly (estimated mastery {pct(m)} → {pct(target)})",
                        state,
                        None,
                    )
                )
        elif t.rule in ("review", "review_turn"):
            value = bkt.update(m, True, self.params.p_slip, self.guess(c), self.params.p_learn)
            state = _answered(self.state, c, value, 1)
            activity = replace(
                self.activity,
                last_practiced={**self.activity.last_practiced, c: self.planner.now()},
            )
            out.append(
                ("review_done", None, 1, f"answer this review question on {name}", state, activity)
            )
        return out

    def counterfactuals(self) -> list[Counterfactual]:
        verified = []
        for kind, target, steps, condition, state, activity in self.candidates():
            outcome = self.rerun(state, activity)
            if (outcome.rule, outcome.concept_id) == (self.trace.rule, self.trace.concept_id):
                continue  # would not change the decision: never show it
            verified.append(
                Counterfactual(
                    kind=kind,
                    concept_id=self.trace.concept_id,
                    target_value=target,
                    steps_needed=steps,
                    condition=condition[0].upper() + condition[1:],
                    outcome=(
                        f"{self.name(outcome.concept_id)} would become normal practice on your "
                        "path instead of a fix-up"
                        if outcome.concept_id == self.trace.concept_id
                        else self.outcome_text(outcome)
                    ),
                    outcome_concept_id=outcome.concept_id,
                )
            )
        return verified


def build_rationale(
    planner: Planner,
    trace: Trace,
    state: LearnerState,
    activity: Activity,
    recommendation_id: uuid.UUID,
) -> Rationale:
    builder = _Builder(planner, trace, state, activity)
    return Rationale(
        recommendation_id=recommendation_id,
        rule=trace.reasons[0].code if trace.rule == "misconception" else RULE_CODE[trace.rule],
        summary=builder.summary(),
        evidence=trace.reasons,
        threshold=trace.threshold,
        alternative=builder.alternative(),
        counterfactuals=builder.counterfactuals(),
    )
