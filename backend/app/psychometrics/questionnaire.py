"""Questionnaire loading and scoring (docs/MODEL_SPEC.md §2.1)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.contracts.learner import TRAIT_NAMES, TraitName

LIKERT_MIN, LIKERT_MAX = 1, 5
MIN_ANSWERS_PER_TRAIT = 2  # fewer than this -> the trait keeps its neutral prior


class QuestionnaireItem(BaseModel):
    id: str
    trait: TraitName
    text: str
    reverse_scored: bool = False
    source: str


class QuestionnaireItemPublic(BaseModel):
    """What the learner sees: no trait, scoring direction or citation."""

    id: str
    text: str


class TraitScore(BaseModel):
    mean: float = Field(ge=0.0, le=1.0)  # 0..1, from the 1..5 average
    n_answered: int


def load_questionnaire(path: Path) -> list[QuestionnaireItem]:
    if not path.exists():
        return []
    return [QuestionnaireItem.model_validate(i) for i in yaml.safe_load(path.read_text())["items"]]


def keyed_value(item: QuestionnaireItem, value: int) -> int:
    """The answer with reverse-scored items flipped, so higher always means more of the trait."""
    return LIKERT_MAX + LIKERT_MIN - value if item.reverse_scored else value


def score(items: list[QuestionnaireItem], answers: dict[str, int]) -> dict[TraitName, TraitScore]:
    """Per-trait mean in [0, 1]. Raises ValueError for unknown items or out-of-range values.
    Traits with fewer than MIN_ANSWERS_PER_TRAIT answers are omitted."""
    by_id = {i.id: i for i in items}
    unknown = set(answers) - set(by_id)
    if unknown:
        raise ValueError(f"unknown questionnaire items: {sorted(unknown)}")
    keyed: dict[TraitName, list[int]] = {t: [] for t in TRAIT_NAMES}
    for item_id, value in answers.items():
        if not LIKERT_MIN <= value <= LIKERT_MAX:
            raise ValueError(f"{item_id}: answer {value} is outside {LIKERT_MIN}..{LIKERT_MAX}")
        item = by_id[item_id]
        keyed[item.trait].append(keyed_value(item, value))
    return {
        trait: TraitScore(
            mean=(sum(values) / len(values) - LIKERT_MIN) / (LIKERT_MAX - LIKERT_MIN),
            n_answered=len(values),
        )
        for trait, values in keyed.items()
        if len(values) >= MIN_ANSWERS_PER_TRAIT
    }
