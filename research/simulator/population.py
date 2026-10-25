"""Synthetic learners with known ("true") traits and knowledge, and how they respond.

The explanation response model uses the same functional form the bandit assumes
(docs/MODEL_SPEC.md §2.2), so this is a *well-specified* world: it tests whether the loop can
recover preferences that really exist, not whether that functional form is right for real students.
"""

from dataclasses import dataclass, field

import numpy as np

from app.contracts.graph import Item
from app.contracts.learner import TRAIT_NAMES, TraitName
from app.graph.service import GraphSnapshot
from app.learner_model.bandit import KAPPA, StyleChoice, features, known_offset
from app.psychometrics.questionnaire import QuestionnaireItem


@dataclass(frozen=True)
class ResponseConfig:
    slip: float = 0.1
    learn_from_practice: float = 0.15  # true BKT transition after an attempt
    learn_from_explanation: float = 0.2  # chance an explanation teaches an unknown concept...
    explanation_fit_gain: float = 1.0  # ...plus this times the style fit q (can go to 0)
    clarity_prompt_rate: float = 1 / 3  # matches the M2 design: rating asked on ~1 in 3
    clarity_noise: float = 0.8
    dismiss_rate: float = 0.12
    confidence_rate: float = 0.5
    questionnaire_noise: float = 0.9  # SD of one Likert answer around 1 + 4·self-view
    # SD of the gap between how learners see themselves and what actually helps them
    self_report_gap: float = 0.0
    max_quit_after_wrong: float = 0.35  # quit chance after a wrong answer at persistence 0
    session_steps: int = 15


@dataclass
class SyntheticLearner:
    traits: dict[TraitName, float]  # true traits: what actually drives behaviour
    self_view: dict[TraitName, float]  # what the learner reports on the questionnaire
    ability: float
    known: dict[str, bool] = field(default_factory=dict)

    @property
    def theta(self) -> np.ndarray:
        """True bandit coefficients (intercept 0) in the model's trait units."""
        return np.array(
            [0.0]
            + [
                KAPPA * (2 * self.traits[t] - 1)
                for t in ("abstraction_preference", "load_tolerance", "depth_preference")
            ]
        )

    def fit(self, style: StyleChoice) -> float:
        """True expected explanation quality q for a style (higher is better)."""
        return float(self.theta @ features(style)) + known_offset(style)

    def mastery_fraction(self) -> float:
        return sum(self.known.values()) / len(self.known)


def make_population(
    n: int,
    graph: GraphSnapshot,
    rng: np.random.Generator,
    null_preferences: bool = False,
    self_report_gap: float = 0.0,
) -> list[SyntheticLearner]:
    """Traits ~ Beta(2, 2) (centred, rarely extreme); with null_preferences the three style traits
    are exactly 0.5, i.e. no style is truly better for anyone. self_view = traits + N(0, gap)."""
    learners = []
    for _ in range(n):
        traits = {t: float(rng.beta(2, 2)) for t in TRAIT_NAMES}
        if null_preferences:
            traits.update(abstraction_preference=0.5, load_tolerance=0.5, depth_preference=0.5)
        self_view = {
            t: float(np.clip(v + rng.normal(0, self_report_gap), 0, 1)) if self_report_gap else v
            for t, v in traits.items()
        }
        learner = SyntheticLearner(
            traits=traits, self_view=self_view, ability=float(rng.uniform(0.3, 0.8))
        )
        for concept_id in graph.topological_order:
            prereqs = graph.prerequisites(concept_id)
            share = sum(learner.known[p] for p in prereqs) / len(prereqs) if prereqs else 1.0
            learner.known[concept_id] = bool(rng.random() < learner.ability * share)
        learners.append(learner)
    return learners


def questionnaire_answers(
    learner: SyntheticLearner,
    items: list[QuestionnaireItem],
    rng: np.random.Generator,
    cfg: ResponseConfig,
) -> dict[str, int]:
    answers = {}
    for item in items:
        raw = 1 + 4 * learner.self_view[item.trait] + rng.normal(0, cfg.questionnaire_noise)
        value = int(np.clip(round(raw), 1, 5))
        answers[item.id] = 6 - value if item.reverse_scored else value
    return answers


def answer(
    learner: SyntheticLearner, item: Item, rng: np.random.Generator, cfg: ResponseConfig
) -> tuple[str, bool]:
    """Response text and correctness. Wrong MCQ answers prefer a misconception distractor."""
    p_correct = 1 - cfg.slip if learner.known[item.concept_id] else 1 / max(2, len(item.options))
    correct = bool(rng.random() < p_correct)
    if correct:
        return item.answer, True
    distractors = [o for o in item.options if o != item.answer] or ["?"]
    mapped = [o for o in distractors if o in item.distractor_misconceptions]
    pick = (
        mapped[0] if mapped and rng.random() < 0.5 else distractors[rng.integers(len(distractors))]
    )
    return pick, False


def practice(learner: SyntheticLearner, concept_id: str, rng: np.random.Generator, cfg) -> None:
    if not learner.known[concept_id] and rng.random() < cfg.learn_from_practice:
        learner.known[concept_id] = True


def read_explanation(
    learner: SyntheticLearner,
    concept_id: str,
    style: StyleChoice,
    rng: np.random.Generator,
    cfg: ResponseConfig,
) -> tuple[int | None, bool]:
    """Reading may teach the concept (more likely when the style fits). Returns the clarity rating
    (if the learner was asked and answered) and whether they dismissed it quickly."""
    q = learner.fit(style)
    p_learn = np.clip(cfg.learn_from_explanation + cfg.explanation_fit_gain * q, 0, 1)
    if not learner.known[concept_id] and rng.random() < p_learn:
        learner.known[concept_id] = True
    clarity = None
    if rng.random() < cfg.clarity_prompt_rate:
        raw = 3 + 2 * q / KAPPA + rng.normal(0, cfg.clarity_noise)
        clarity = int(np.clip(round(raw), 1, 5))
    dismissed = bool(rng.random() < cfg.dismiss_rate * (1.5 if q < 0 else 1.0))
    return clarity, dismissed


def confidence(
    learner: SyntheticLearner, concept_id: str, rng: np.random.Generator, cfg: ResponseConfig
) -> int | None:
    if rng.random() >= cfg.confidence_rate:
        return None
    knows = 1.0 if learner.known[concept_id] else 0.0
    raw = 1 + 4 * (0.6 * learner.traits["self_efficacy"] + 0.4 * knows) + rng.normal(0, 0.6)
    return int(np.clip(round(raw), 1, 5))


def quits_after_wrong(
    learner: SyntheticLearner, rng: np.random.Generator, cfg: ResponseConfig
) -> bool:
    return bool(rng.random() < cfg.max_quit_after_wrong * (1 - learner.traits["persistence"]))
