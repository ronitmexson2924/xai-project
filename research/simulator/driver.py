"""Runs synthetic learners through the *real* LearnerModel and Planner (in-process, Postgres),
with the fake explainer standing in for Mit's Module B.

Everything happens inside the caller's transaction; the caller rolls it back, so a run never
leaves data behind. The same synthetic population is used in every arm (paired design).
"""

import copy
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import numpy as np
from sqlalchemy.orm import Session

from app.contracts.explanation import ExplanationFeedbackSummary, ExplanationRequest
from app.contracts.fakes import FakeExplainer
from app.contracts.learner import AttemptRecord, ExperimentArm, TraitName
from app.db import models as m
from app.graph.seed import seed as seed_content
from app.graph.service import GraphSnapshot
from app.learner_model.bandit import ALL_STYLES, StyleChoice, best_style
from app.learner_model.service import LearnerModel
from app.learner_model.traits import PRIOR_VARIANCE
from app.planner.service import Planner
from app.planner.style import EPSILON_MIN, candidates
from simulator import population as pop
from simulator.world import simulation_bundle

ARMS: tuple[ExperimentArm, ...] = ("generic", "static_personalized", "closed_loop")
STYLE_TRAITS: tuple[TraitName, ...] = (
    "abstraction_preference",
    "load_tolerance",
    "depth_preference",
)
STEP_TIME = timedelta(minutes=2)
SESSION_BREAK = timedelta(days=1)
T0 = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


@dataclass(frozen=True)
class RunConfig:
    arms: tuple[ExperimentArm, ...] = ARMS
    learners_per_arm: int = 40
    steps: int = 60
    seed: int = 0
    epsilon: float = EPSILON_MIN
    questionnaire_variance: float = PRIOR_VARIANCE
    null_preferences: bool = False
    microcheck_rate: float = 0.8
    behaviour_alpha: float = 0.0  # LearnerModel default (off); see MODEL_SPEC §2.3
    response: pop.ResponseConfig = field(default_factory=pop.ResponseConfig)


@dataclass(frozen=True)
class StepRecord:
    arm: str
    learner: int
    step: int
    style: StyleChoice
    source: str
    fit: float  # true quality of the chosen style
    best_fit: float  # true quality of the best style for this learner
    differs_from_greedy: bool  # chosen style != argmax of the posterior mean
    followup_correct: bool | None
    main_correct: bool
    estimated: dict[TraitName, float]  # reported trait means *before* this step
    true: dict[TraitName, float]
    mastery_fraction: float  # true fraction of concepts known after this step


def simulate(session: Session, cfg: RunConfig) -> tuple[list[StepRecord], dict]:
    bundle = simulation_bundle()
    seed_content(session, bundle)
    graph = GraphSnapshot.from_bundle(bundle)
    rng = np.random.default_rng(cfg.seed)
    base_population = pop.make_population(
        cfg.learners_per_arm,
        graph,
        rng,
        null_preferences=cfg.null_preferences,
        self_report_gap=cfg.response.self_report_gap,
    )
    questionnaire = LearnerModel(session, graph).questionnaire_items()
    answers = [  # drawn once per learner, so every arm sees the same questionnaire answers
        pop.questionnaire_answers(
            learner, questionnaire, np.random.default_rng([cfg.seed, i, 99]), cfg.response
        )
        for i, learner in enumerate(base_population)
    ]
    initial_mastery = [learner.mastery_fraction() for learner in base_population]
    records: list[StepRecord] = []
    final: dict[tuple[str, int], dict[TraitName, float]] = {}
    for arm_index, arm in enumerate(cfg.arms):
        for index, base in enumerate(base_population):
            learner = copy.deepcopy(base)
            learner_rng = np.random.default_rng([cfg.seed, arm_index, index])
            steps, final[(arm, index)] = _run_learner(
                session, graph, cfg, arm, index, learner, answers[index], learner_rng
            )
            records += steps
    return records, {"initial_mastery": initial_mastery, "final_estimates": final}


def _run_learner(
    session: Session,
    graph: GraphSnapshot,
    cfg: RunConfig,
    arm: ExperimentArm,
    index: int,
    learner: pop.SyntheticLearner,
    answers: dict[str, int],
    rng: np.random.Generator,
) -> tuple[list[StepRecord], dict[TraitName, float]]:
    rcfg = cfg.response
    clock = [T0]
    user_id = uuid.uuid4()
    session.add(m.User(id=user_id, email=f"{user_id}@sim", password_hash="-", display_name="sim"))
    session.flush()
    session.add(m.ExperimentAssignment(user_id=user_id, arm=arm))
    session.flush()

    model = LearnerModel(
        session,
        graph,
        questionnaire_variance=cfg.questionnaire_variance,
        behaviour_alpha=cfg.behaviour_alpha,
    )
    planner = Planner(
        session, graph, model, seed=cfg.seed + index, now=lambda: clock[0], epsilon=cfg.epsilon
    )
    explainer = FakeExplainer(graph)  # duck-typed: only needs get_concept()
    model.init_from_questionnaire(user_id, answers)
    test_rng = np.random.default_rng([cfg.seed, ARMS.index(arm), index, 7])  # separate stream
    _take_test(model, graph, learner, user_id, "pretest", clock[0], test_rng, rcfg)
    best_fit = max(learner.fit(s) for s in ALL_STYLES)

    records = []
    steps_in_session = 0
    for step in range(cfg.steps):
        state = model.get_state(user_id)
        estimated = {t: e.mean for t, e in state.traits.traits.items()}
        rec = planner.next_step(state)
        concept_id = rec.target_concept_id
        style, source = planner.choose_style(state, concept_id)
        choice: StyleChoice = (style.example_first, style.length, style.depth)
        greedy = best_style(model.bandit_posterior(user_id).mean, candidates(state.affect))
        check = graph.items_for_concept(concept_id, microcheck=True)[0]

        explanation = explainer.explain(
            ExplanationRequest(
                user_id=user_id,
                recommendation_id=rec.id,
                concept_ids=[concept_id],
                reasons=rec.reasons,
                style=style,
                style_source=source,
                followup_item_id=check.id,
            )
        )
        session.add(
            m.ExplanationRow(
                id=explanation.id,
                recommendation_id=rec.id,
                user_id=user_id,
                concept_ids=[concept_id],
                style=style.model_dump(),
                style_source=source,
                body_markdown=explanation.body_markdown,
                source=explanation.source,
                followup_item_id=check.id,
                prompt_version=explanation.prompt_version,
            )
        )
        session.flush()

        clarity, dismissed = pop.read_explanation(learner, concept_id, choice, rng, rcfg)
        followup: bool | None = None
        if rng.random() < cfg.microcheck_rate:
            response, followup = pop.answer(learner, check, rng, rcfg)
            model.apply_attempt(
                AttemptRecord(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    item_id=check.id,
                    concept_id=concept_id,
                    response=response,
                    correct=followup,
                    latency_ms=int(rng.integers(4000, 30000)),
                    explanation_id=explanation.id,
                    created_at=clock[0],
                )
            )
            pop.practice(learner, concept_id, rng, rcfg)
        summary = ExplanationFeedbackSummary(
            explanation_id=explanation.id,
            user_id=user_id,
            concept_ids=[concept_id],
            style=style,
            style_source=source,
            effective_dwell_ms=2000 if dismissed else int(rng.integers(10_000, 60_000)),
            clarity_rating=clarity,
            followup_correct=followup,
            dismissed_quickly=dismissed,
        )
        # what Mit's telemetry stores (explanation_feedback), so analyses see production-like logs
        session.add(
            m.ExplanationFeedbackRow(
                explanation_id=explanation.id, summary=summary.model_dump(mode="json")
            )
        )
        model.apply_explanation_feedback(summary)

        item = graph.get_item(rec.item_id)
        clock[0] += STEP_TIME / 2
        response, correct = pop.answer(learner, item, rng, rcfg)
        model.apply_attempt(
            AttemptRecord(
                id=uuid.uuid4(),
                user_id=user_id,
                item_id=item.id,
                concept_id=item.concept_id,
                response=response,
                correct=correct,
                latency_ms=int(rng.integers(2000, 40000)),
                confidence=pop.confidence(learner, item.concept_id, rng, rcfg),
                recommendation_id=rec.id,
                created_at=clock[0],
            )
        )
        pop.practice(learner, item.concept_id, rng, rcfg)

        records.append(
            StepRecord(
                arm=arm,
                learner=index,
                step=step,
                style=choice,
                source=source,
                fit=learner.fit(choice),
                best_fit=best_fit,
                differs_from_greedy=choice != greedy,
                followup_correct=followup,
                main_correct=correct,
                estimated=estimated,
                true=dict(learner.traits),
                mastery_fraction=learner.mastery_fraction(),
            )
        )

        steps_in_session += 1
        clock[0] += STEP_TIME / 2
        if steps_in_session >= rcfg.session_steps or (
            not correct and pop.quits_after_wrong(learner, rng, rcfg)
        ):
            clock[0] += SESSION_BREAK
            steps_in_session = 0
    _take_test(model, graph, learner, user_id, "posttest", clock[0], test_rng, rcfg)
    final = {t: e.mean for t, e in model.get_state(user_id).traits.traits.items()}
    return records, final


def _take_test(model, graph, learner, user_id, phase, at, rng, rcfg) -> None:
    """Answer every pre/post-test item from the learner's current true knowledge."""
    for item_id in sorted(i for i in graph.test_item_ids if i.startswith(f"{phase}-")):
        item = graph.get_item(item_id)
        response, correct = pop.answer(learner, item, rng, rcfg)
        model.record_test_attempt(
            AttemptRecord(
                id=uuid.uuid4(),
                user_id=user_id,
                item_id=item_id,
                concept_id=item.concept_id,
                response=response,
                correct=correct,
                latency_ms=15_000,
                created_at=at,
            )
        )
