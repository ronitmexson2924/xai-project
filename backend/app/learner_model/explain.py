"""Open-learner-model explanations: why the system believes what it does about a learner (XAI E4)
and what one update changed (E5). Built from the `state_updates` audit log, so every statement
points at evidence the model actually used (docs/XAI_DESIGN.md)."""

from uuid import UUID

from sqlalchemy import select

from app.contracts.learner import TRAIT_NAMES, StateDelta, TraitName
from app.contracts.xai import BeliefExplanation, ChangeNotice, Confidence
from app.db import models as m
from app.learner_model.service import LearnerModel

MIN_MASTERY_CHANGE = 0.05  # smaller mastery moves are not worth a notice
MIN_TRAIT_CHANGE = 0.02
TOP_EVIDENCE = 3

TRAIT_LABELS: dict[TraitName, str] = {
    "abstraction_preference": "Examples first or rules first",
    "load_tolerance": "Explanation length",
    "depth_preference": "How it works or why it works",
    "persistence": "Keeping going after a hard question",
    "self_efficacy": "Confidence with DSA",
}
# Directions for E5 notices: (trait went down, trait went up)
TRAIT_SHIFTS: dict[TraitName, tuple[str, str]] = {
    "abstraction_preference": (
        "We'll lean a bit more towards starting with an example.",
        "We'll lean a bit more towards starting with the general rule.",
    ),
    "load_tolerance": (
        "We'll keep explanations a bit shorter.",
        "We'll allow a bit more detail in explanations.",
    ),
    "depth_preference": (
        "We'll focus a bit more on how to use things.",
        "We'll focus a bit more on why things work.",
    ),
}


def pct(x: float) -> str:
    return f"{round(100 * x)}%"


def mastery_confidence(n_attempts: int) -> Confidence:
    if n_attempts < 5:
        return "tentative"
    return "moderate" if n_attempts < 12 else "confident"


def trait_confidence(n_observations: int, variance: float) -> Confidence:
    if n_observations < 5 or variance > 0.03:
        return "tentative"
    return "moderate" if n_observations < 15 else "confident"


def _trait_summary(trait: TraitName, mean: float) -> str:
    if trait == "abstraction_preference":
        if mean < 0.4:
            return "Explanations that start with an example seem to work better for you."
        if mean > 0.6:
            return "Explanations that start with the general rule seem to work better for you."
        return "No clear preference yet between starting with an example or with the rule."
    if trait == "load_tolerance":
        if mean < 0.35:
            return "Shorter, step-by-step explanations seem to suit you."
        if mean > 0.65:
            return "Longer, detailed explanations seem to suit you."
        return "Medium-length explanations seem to suit you."
    if trait == "depth_preference":
        if mean < 0.4:
            return "Explanations focused on how to use things seem to suit you."
        if mean > 0.6:
            return "Explanations that show why things work seem to suit you."
        return "No clear preference yet between 'how' and 'why' explanations."
    return (
        "Comes from your questionnaire. It only changes how encouraging our wording is and is "
        "never used to judge you or to choose your topics."
    )


class BeliefExplainer:
    def __init__(self, model: LearnerModel) -> None:
        self.model = model
        self.session = model.session
        self.graph = model.graph

    def _updates(self, user_id: UUID) -> list[m.StateUpdateRow]:
        return list(
            self.session.scalars(
                select(m.StateUpdateRow)
                .where(m.StateUpdateRow.user_id == user_id)
                .order_by(m.StateUpdateRow.created_at.desc(), m.StateUpdateRow.id.desc())
            )
        )

    def explain_belief(self, user_id: UUID, subject: str) -> BeliefExplanation:
        state = self.model.get_state(user_id)  # raises LookupError for unknown/deleted users
        if subject in self.graph.depth:
            return self._concept(user_id, subject, state)
        if subject in TRAIT_NAMES:
            return self._trait(user_id, subject, state)
        raise LookupError(f"unknown subject {subject}")

    def _concept(self, user_id: UUID, concept_id: str, state) -> BeliefExplanation:
        name = self.graph.get_concept(concept_id).name
        value = self.model.effective_mastery(state)[concept_id]
        record = state.mastery.get(concept_id)
        n = record.n_attempts if record else 0
        if n == 0:
            summary = (
                f"You haven't answered questions on {name} yet. We estimate {pct(value)} from how "
                "you're doing on the topics it builds on."
            )
        else:
            summary = (
                f"Estimated mastery {pct(value)}, from your {n} answer{'s' if n != 1 else ''} "
                f"on {name}."
            )
            for mid in record.misconception_ids:
                summary += f' Open issue: "{self.graph.misconception(mid).description}"'
            if record.misconception_suspicion >= 0.5:
                summary += " Recent explanations of it didn't seem to land, so we'll revisit it."

        attempt_updates = [
            u
            for u in self._updates(user_id)
            if u.source == "attempt" and concept_id in u.delta.get("mastery_changes", {})
        ]
        correct = {
            str(a.id): a.correct
            for a in self.session.scalars(
                select(m.AttemptRow).where(
                    m.AttemptRow.id.in_([UUID(u.source_id) for u in attempt_updates])
                )
            )
        }
        biggest = sorted(
            attempt_updates,
            key=lambda u: abs(
                u.delta["mastery_changes"][concept_id][1]
                - u.delta["mastery_changes"][concept_id][0]
            ),
            reverse=True,
        )[:TOP_EVIDENCE]
        evidence = []
        for u in sorted(biggest, key=lambda u: u.created_at, reverse=True):
            before, after = u.delta["mastery_changes"][concept_id]
            outcome = "correct" if correct.get(u.source_id) else "wrong"
            verb = "raised" if after >= before else "lowered"
            evidence.append(
                f"{u.created_at:%d %b}: a {outcome} answer {verb} it from {pct(before)} to "
                f"{pct(after)}"
            )
        return BeliefExplanation(
            subject=concept_id,
            label=name,
            value=value,
            confidence=mastery_confidence(n),
            summary=summary,
            top_evidence=evidence,
        )

    def _trait(self, user_id: UUID, trait: TraitName, state) -> BeliefExplanation:
        estimate = state.traits.traits[trait]
        updates = [u for u in self._updates(user_id) if trait in u.delta.get("trait_changes", {})]
        biggest = sorted(
            updates,
            key=lambda u: abs(
                u.delta["trait_changes"][trait][1] - u.delta["trait_changes"][trait][0]
            ),
            reverse=True,
        )[:TOP_EVIDENCE]
        source_text = {
            "questionnaire": "your questionnaire answers set it",
            "explanation_feedback": "your feedback on an explanation moved it",
            "attempt": "how you kept going after a hard question moved it",
        }
        evidence = []
        for u in sorted(biggest, key=lambda u: u.created_at, reverse=True):
            before, after = u.delta["trait_changes"][trait]
            change = (
                f"to {pct(after)}"
                if u.source == "questionnaire"
                else f"from {pct(before)} to {pct(after)}"
            )
            evidence.append(f"{u.created_at:%d %b}: {source_text[u.source]} {change}")
        n = estimate.n_observations
        summary = _trait_summary(trait, estimate.mean)
        if trait in TRAIT_SHIFTS:
            summary += (
                f" Based on {n} explanation{'s' if n != 1 else ''} with feedback."
                if n
                else " So far this comes only from your questionnaire."
            )
        return BeliefExplanation(
            subject=trait,
            label=TRAIT_LABELS[trait],
            value=estimate.mean,
            confidence=trait_confidence(n, estimate.variance),
            summary=summary,
            top_evidence=evidence,
        )

    # --- E5 -------------------------------------------------------------------------------------

    def explain_change(self, delta: StateDelta) -> ChangeNotice:
        messages: list[str] = []
        if delta.source == "questionnaire":
            messages.append(
                "Thanks! Your answers set how we'll start explaining things. Your feedback on "
                "explanations will fine-tune it."
            )
            return ChangeNotice(source=delta.source, messages=messages)

        for concept_id, (before, after) in delta.mastery_changes.items():
            if abs(after - before) >= MIN_MASTERY_CHANGE:
                direction = "up" if after > before else "down"
                messages.append(
                    f"Your estimated mastery of {self.graph.get_concept(concept_id).name} went "
                    f"{direction} from {pct(before)} to {pct(after)}."
                )
        for note in delta.notes:
            if note.startswith("misconception flagged: "):
                mid = note.removeprefix("misconception flagged: ")
                messages.append(
                    "That answer matches a common mistake: "
                    f'"{self.graph.misconception(mid).description}" We\'ll help you with it next.'
                )
            elif note.startswith("misconceptions cleared: "):
                mid = note.removeprefix("misconceptions cleared: ").split(", ")[0]
                concept = self.graph.misconception(mid).concept_id
                messages.append(
                    f"The mistake we flagged on {self.graph.get_concept(concept).name} looks "
                    "sorted now."
                )
            elif note.startswith("misconception suspicion "):
                concept, change = note.removeprefix("misconception suspicion ").split(": ")
                before, after = (float(x) for x in change.split(" -> "))
                if after > before:
                    messages.append(
                        f"That explanation of {self.graph.get_concept(concept).name} didn't "
                        "seem to land, so we'll come back to it."
                    )
        for trait, (before, after) in delta.trait_changes.items():
            if trait in TRAIT_SHIFTS and abs(after - before) >= MIN_TRAIT_CHANGE:
                messages.append(TRAIT_SHIFTS[trait][int(after > before)])
        return ChangeNotice(source=delta.source, messages=messages)
