"""The performance model's prediction for one recommended question, explained four ways.

The features are rebuilt from the logs as they were when the question was recommended (before
the answer), so the explanation is of the prediction the model would have made at that moment,
whether or not the learner has answered since. Explanations are cached per recommendation: the
inputs never change once the recommendation exists.
"""

from collections import OrderedDict
from datetime import datetime
from threading import Lock
from typing import Any
from uuid import UUID

import numpy as np
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.graph.service import GraphSnapshot
from app.ml import explain
from app.ml.features import FEATURE_NAMES, FEATURES, replay
from app.ml.model import PerformanceModel, load

LABELS = {f.name: f.label for f in FEATURES}
METHOD_TITLES = {
    "shap": "SHAP",
    "lime": "LIME",
    "lrp": "LRP",
}
METHOD_ABOUT = {
    "shap": "How much each factor moved the predicted chance away from the average learner's "
    "(Shapley values: the contributions add up exactly to the prediction).",
    "lime": "A simple straight-line model fitted to the network's answers for learners similar "
    "to you; its R² says how well that simple model matches the network here.",
    "lrp": "The network's output traced back through its layers onto its inputs (layer-wise "
    "relevance propagation), in log-odds.",
}


class FeatureValue(BaseModel):
    name: str
    label: str
    value: float
    display: str


class MethodAttribution(BaseModel):
    method: str
    title: str
    about: str
    unit: str
    base: float
    output: float
    fidelity: float | None
    contributions: dict[str, float]


class CounterfactualChange(BaseModel):
    name: str
    label: str
    now: str
    then: str


class CounterfactualOut(BaseModel):
    p_correct: float
    changes: list[CounterfactualChange]


class ModelSummary(BaseModel):
    name: str
    architecture: str
    trained_on: str
    test_auc: float
    bkt_auc: float


class ModelInsight(BaseModel):
    recommendation_id: UUID
    concept_id: str
    concept_name: str
    p_correct: float
    summary: str
    features: list[FeatureValue]
    attributions: list[MethodAttribution]
    counterfactuals: list[CounterfactualOut]
    agreement: dict[str, float]
    notes: list[str]
    answered_correctly: bool | None  # None until the learner has answered
    model: ModelSummary


def display(name: str, value: float) -> str:
    if name in ("mastery", "prereq_mean", "prereq_min", "recent_accuracy", "overall_accuracy"):
        return f"{value:.0%}"
    if name == "guess_rate":
        return f"{value:.0%}" if value else "no options"
    if name in ("self_efficacy", "persistence"):
        return f"{value:.2f}"
    if name == "misconception":
        return "yes" if value >= 0.5 else "no"
    if name == "days_since_practice":
        return "never practised" if value >= 30 else f"{value:.1f} days"
    if name == "streak":
        return f"{int(value):+d}" if value else "0"
    return f"{int(round(value))}"


def summarise(e: explain.Explanation) -> str:
    """One plain sentence from SHAP (the method whose numbers add up to the prediction)."""
    shap_values = e.attributions["shap"].values
    order = np.argsort(-np.abs(shap_values))
    up = [LABELS[FEATURE_NAMES[i]].lower() for i in order if shap_values[i] > 0.005][:2]
    down = [LABELS[FEATURE_NAMES[i]].lower() for i in order if shap_values[i] < -0.005][:2]
    parts = []
    if up:
        parts.append("raised mostly by " + " and ".join(up))
    if down:
        parts.append("lowered mostly by " + " and ".join(down))
    reason = "; ".join(parts) if parts else "close to the average learner's"
    return f"The model put your chance of answering correctly at {e.p_correct:.0%}: {reason}."


def _to_insight(
    e: explain.Explanation,
    recommendation_id: UUID,
    concept_id: str,
    concept_name: str,
    model: PerformanceModel,
) -> ModelInsight:
    card = model.card
    metrics = card.get("test_metrics", {})
    return ModelInsight(
        recommendation_id=recommendation_id,
        concept_id=concept_id,
        concept_name=concept_name,
        p_correct=e.p_correct,
        summary=summarise(e),
        features=[
            FeatureValue(name=f.name, label=f.label, value=float(v), display=display(f.name, v))
            for f, v in zip(FEATURES, e.x, strict=True)
        ],
        attributions=[
            MethodAttribution(
                method=a.method,
                title=METHOD_TITLES[a.method],
                about=METHOD_ABOUT[a.method],
                unit=a.unit,
                base=a.base,
                output=a.output,
                fidelity=a.fidelity,
                contributions=dict(zip(FEATURE_NAMES, map(float, a.values), strict=True)),
            )
            for a in e.attributions.values()
        ],
        counterfactuals=[
            CounterfactualOut(
                p_correct=cf.p_correct,
                changes=[
                    CounterfactualChange(
                        name=name, label=LABELS[name], now=display(name, a), then=display(name, b)
                    )
                    for name, (a, b) in cf.changes.items()
                ],
            )
            for cf in e.counterfactuals
        ],
        agreement=e.agreement,
        notes=e.notes,
        answered_correctly=None,
        model=ModelSummary(
            name=card.get("name", "Performance model"),
            architecture=card.get("architecture", ""),
            trained_on=card.get("trained_on", ""),
            test_auc=metrics.get("neural network (this model)", {}).get("auc", float("nan")),
            bkt_auc=metrics.get("BKT (the learner model)", {}).get("auc", float("nan")),
        ),
    )


_cache: OrderedDict[UUID, ModelInsight] = OrderedDict()
_cache_lock = Lock()
CACHE_SIZE = 512


def insight_for_recommendation(
    session: Session, graph: GraphSnapshot, user_id: UUID, recommendation_id: UUID
) -> ModelInsight:
    """Raises LookupError if the recommendation is not this user's or has no question."""
    row = session.get(m.RecommendationRow, recommendation_id)
    if row is None or row.user_id != user_id or row.item_id is None:
        raise LookupError("recommendation")
    try:
        item = graph.get_item(row.item_id)
    except KeyError:
        raise LookupError("item") from None
    answered = session.scalar(
        select(m.AttemptRow.correct).where(m.AttemptRow.recommendation_id == recommendation_id)
    )

    with _cache_lock:
        cached = _cache.get(recommendation_id)
    if cached is None:
        model = load()
        created: datetime = row.created_at
        state, _rows = replay(session, graph, user_id, until=created)
        e = explain.explain(model, state.features(item, created))
        concept = graph.get_concept(item.concept_id)
        cached = _to_insight(e, recommendation_id, concept.id, concept.name, model)
        with _cache_lock:
            _cache[recommendation_id] = cached
            while len(_cache) > CACHE_SIZE:
                _cache.popitem(last=False)
    return cached.model_copy(update={"answered_correctly": answered})


def model_card() -> dict[str, Any]:
    model = load()
    return {**model.card, "features": [{"name": f.name, "label": f.label} for f in FEATURES]}
