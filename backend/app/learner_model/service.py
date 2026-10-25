"""LearnerModelService implementation (Module A + the update half of Module C).

Methods flush but never commit: the caller (an API request, the simulator) owns the transaction.
Every apply_* call is idempotent on (source, source_id) via the state_updates table.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.explanation import ExplanationFeedbackSummary
from app.contracts.learner import (
    TRAIT_NAMES,
    AffectiveState,
    AttemptRecord,
    ConceptMastery,
    ExperimentArm,
    LearnerState,
    LearnerTraits,
    StateDelta,
    StateUpdateSource,
    TraitEstimate,
)
from app.db import models as m
from app.graph.service import GraphSnapshot
from app.learner_model import bkt
from app.learner_model.bandit import BanditPosterior
from app.learner_model.traits import PRIOR_VARIANCE, neutral_traits
from app.psychometrics.questionnaire import QuestionnaireItem, score

MISCONCEPTION_CLEAR_STREAK = 2  # consecutive correct attempts that clear a misconception flag
DEFAULT_ARM: ExperimentArm = "generic"  # used only if a user somehow has no assignment


class LearnerModel:
    def __init__(
        self, session: Session, graph: GraphSnapshot, params: bkt.BKTParams = bkt.DEFAULT_PARAMS
    ) -> None:
        self.session = session
        self.graph = graph
        self.params = params

    # --- reads -----------------------------------------------------------------------------------

    def get_state(self, user_id: UUID) -> LearnerState:
        row = self.session.execute(
            select(m.LearnerTraitsRow, m.LearnerAffectRow, m.ExperimentAssignment.arm)
            .select_from(m.User)
            .outerjoin(m.LearnerTraitsRow, m.LearnerTraitsRow.user_id == m.User.id)
            .outerjoin(m.LearnerAffectRow, m.LearnerAffectRow.user_id == m.User.id)
            .outerjoin(m.ExperimentAssignment, m.ExperimentAssignment.user_id == m.User.id)
            .where(m.User.id == user_id)
        ).one_or_none()
        if row is None:
            raise LookupError(f"unknown user {user_id}")
        traits_row, affect_row, arm = row

        mastery = {
            r.concept_id: ConceptMastery(
                concept_id=r.concept_id,
                p_mastery=r.p_mastery,
                n_attempts=r.n_attempts,
                misconception_ids=list(r.misconception_ids),
                misconception_suspicion=r.misconception_suspicion,
            )
            for r in self.session.scalars(
                select(m.LearnerConceptStateRow).where(m.LearnerConceptStateRow.user_id == user_id)
            )
        }
        traits = (
            LearnerTraits(traits=traits_row.traits, version=traits_row.version)
            if traits_row is not None
            else neutral_traits()
        )
        affect = (
            AffectiveState(
                engagement=affect_row.engagement,
                frustration=affect_row.frustration,
                fatigue=affect_row.fatigue,
            )
            if affect_row is not None
            else AffectiveState()
        )
        return LearnerState(
            user_id=user_id,
            arm=arm or DEFAULT_ARM,
            mastery=mastery,
            traits=traits,
            affect=affect,
            total_attempts=sum(c.n_attempts for c in mastery.values()),
        )

    def effective_mastery(self, state: LearnerState) -> dict[str, float]:
        """Mastery for every concept, filling unattempted ones with the prerequisite-based prior."""
        known = {cid: c.p_mastery for cid, c in state.mastery.items()}
        return bkt.effective_mastery(self.graph, known, self.params)

    # --- idempotency helpers ---------------------------------------------------------------------

    def _already_applied(self, source: StateUpdateSource, source_id: str) -> StateDelta | None:
        row = self.session.scalar(
            select(m.StateUpdateRow).where(
                m.StateUpdateRow.source == source, m.StateUpdateRow.source_id == source_id
            )
        )
        return StateDelta.model_validate(row.delta) if row is not None else None

    def _record(self, delta: StateDelta) -> StateDelta:
        self.session.add(
            m.StateUpdateRow(
                user_id=delta.user_id,
                source=delta.source,
                source_id=delta.source_id,
                delta=delta.model_dump(mode="json"),
            )
        )
        self.session.flush()
        return delta

    def _concept_row(self, user_id: UUID, concept_id: str) -> m.LearnerConceptStateRow:
        row = self.session.get(m.LearnerConceptStateRow, (user_id, concept_id))
        if row is None:
            state = self.get_state(user_id)
            row = m.LearnerConceptStateRow(
                user_id=user_id,
                concept_id=concept_id,
                p_mastery=self.effective_mastery(state)[concept_id],
                n_attempts=0,
                streak=0,
                misconception_ids=[],
                misconception_suspicion=0.0,
            )
            self.session.add(row)
        return row

    # --- updates ---------------------------------------------------------------------------------

    def apply_attempt(self, attempt: AttemptRecord) -> StateDelta:
        """Store the graded attempt and update the concept's mastery and misconception flags."""
        source_id = str(attempt.id)
        if (done := self._already_applied("attempt", source_id)) is not None:
            return done

        if self.session.get(m.AttemptRow, attempt.id) is None:
            self.session.add(
                m.AttemptRow(
                    id=attempt.id,
                    user_id=attempt.user_id,
                    item_id=attempt.item_id,
                    recommendation_id=attempt.recommendation_id,
                    explanation_id=attempt.explanation_id,
                    response=attempt.response,
                    correct=attempt.correct,
                    latency_ms=attempt.latency_ms,
                    hints_used=attempt.hints_used,
                    confidence=attempt.confidence,
                    created_at=attempt.created_at,
                )
            )

        item = self.graph.get_item(attempt.item_id)
        row = self._concept_row(attempt.user_id, attempt.concept_id)
        before = row.p_mastery
        row.p_mastery = bkt.update(
            before,
            attempt.correct,
            slip=self.params.p_slip,
            guess=bkt.guess_for(item, self.params),
            p_learn=self.params.p_learn,
        )
        row.n_attempts += 1
        row.streak = max(row.streak, 0) + 1 if attempt.correct else min(row.streak, 0) - 1

        notes: list[str] = []
        flags = list(row.misconception_ids)
        if not attempt.correct and attempt.response in item.distractor_misconceptions:
            misconception_id = item.distractor_misconceptions[attempt.response]
            if misconception_id not in flags:
                flags.append(misconception_id)
                notes.append(f"misconception flagged: {misconception_id}")
        elif attempt.correct and row.streak >= MISCONCEPTION_CLEAR_STREAK and flags:
            notes.append(f"misconceptions cleared: {', '.join(flags)}")
            flags = []
        row.misconception_ids = flags

        delta = StateDelta(
            user_id=attempt.user_id,
            source="attempt",
            source_id=source_id,
            mastery_changes={attempt.concept_id: (before, row.p_mastery)},
            notes=notes,
        )
        return self._record(delta)

    def questionnaire_items(self) -> list[QuestionnaireItem]:
        return [
            QuestionnaireItem(
                id=r.id,
                trait=r.trait,
                text=r.item_text,
                reverse_scored=r.reverse_scored,
                source=r.source,
            )
            for r in self.session.scalars(select(m.QuestionnaireItemRow))
        ]

    def init_from_questionnaire(self, user_id: UUID, answers: dict[str, int]) -> StateDelta:
        """Store answers and set the trait prior (MODEL_SPEC §2.1) and bandit prior (§2.2).
        Taken once per learner: a second submission returns the first result unchanged."""
        source_id = str(user_id)
        if (done := self._already_applied("questionnaire", source_id)) is not None:
            return done

        scores = score(self.questionnaire_items(), answers)
        before = self.get_state(user_id).traits
        for item_id, value in answers.items():
            self.session.merge(
                m.QuestionnaireResponseRow(user_id=user_id, item_id=item_id, value=value)
            )

        priors = dict(before.traits)
        for trait, trait_score in scores.items():
            priors[trait] = TraitEstimate(mean=trait_score.mean, variance=PRIOR_VARIANCE)
        posterior = BanditPosterior.from_trait_priors(priors)
        traits = LearnerTraits(
            traits={**priors, **posterior.reported_traits()}, version=before.version + 1
        )
        self._save_traits(user_id, traits, posterior)
        if self.session.get(m.LearnerAffectRow, user_id) is None:
            self.session.add(m.LearnerAffectRow(user_id=user_id))

        delta = StateDelta(
            user_id=user_id,
            source="questionnaire",
            source_id=source_id,
            trait_changes={
                t: (before.traits[t].mean, traits.traits[t].mean) for t in traits.traits
            },
            notes=[f"traits not scored (too few answers): {', '.join(missing)}"]
            if (missing := sorted(set(TRAIT_NAMES) - set(scores)))
            else [],
        )
        return self._record(delta)

    def _save_traits(
        self, user_id: UUID, traits: LearnerTraits, posterior: BanditPosterior
    ) -> None:
        payload = {t: e.model_dump() for t, e in traits.traits.items()}
        row = self.session.get(m.LearnerTraitsRow, user_id)
        if row is None:
            self.session.add(
                m.LearnerTraitsRow(
                    user_id=user_id,
                    traits=payload,
                    bandit=posterior.to_json(),
                    version=traits.version,
                )
            )
        else:
            row.traits, row.bandit, row.version = payload, posterior.to_json(), traits.version
        self.session.flush()

    def apply_explanation_feedback(self, summary: ExplanationFeedbackSummary) -> StateDelta:
        raise NotImplementedError("task R5")
