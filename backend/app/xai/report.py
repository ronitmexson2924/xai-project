"""`explain_user`: the Explainability section of one learner's report.

What is explained, and by which method (chosen for this model in docs/XAI_DESIGN.md §6):

- The *focus prediction* is the performance model's prediction for the learner's latest
  recommended question, rebuilt from the logs as it was when the question was recommended. It is
  explained by all four methods:
  - SHAP (permutation algorithm; model-agnostic, and exact: base + contributions = prediction).
    TreeExplainer does not apply (not a tree model); Deep/GradientExplainer need PyTorch or
    TensorFlow and this network is plain NumPy; KernelExplainer would be slower and approximate.
  - LIME (tabular): a local linear surrogate, reported with its R² so a poor fit is visible.
    LIME's text explainer does not apply: the model has no free-text input.
  - LRP (epsilon rule on the network's own weights): valid because the model is a neural network.
  - DiCE: a few diverse, realistic counterfactuals that move only what a learner can change.
- The learner's *recent predictions* (their last RECENT answered questions, each with the
  features as they were before that answer) give the person-level views: average SHAP per factor,
  the SHAP decision plot and the LRP heatmap.
- The *profile radar* (traits and mastery per cluster) comes from the learner model itself; those
  estimates have their own exact evidence trail (XAI E4), so they are shown, not re-explained.

Each method runs on its own: if one fails, the report still renders with the others and says so.
Reports are cached per learner until they answer again (or a new question is recommended).
"""

import logging
import math
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, TypeVar
from uuid import UUID

import numpy as np
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.graph.service import GraphSnapshot
from app.learner_model import bkt
from app.learner_model.service import LearnerModel
from app.ml import explain
from app.ml.features import FEATURE_NAMES, FEATURES, replay
from app.ml.model import PerformanceModel, load
from app.ml.service import LABELS, ModelSummary, display, model_summary
from app.xai import metrics
from app.xai.narrative import (
    CLUSTER_LABELS,
    DISCLAIMER,
    MEANINGS,
    TRAIT_LABELS,
    summary_paragraph,
)

logger = logging.getLogger("pcg.xai")

RECENT = 30  # recent predictions used for the person-level views
DICE_TOTAL = 4  # counterfactuals requested (DiCE's paper uses small, diverse sets of 3 to 5)
NEAR_ZERO = 1e-3  # a contribution smaller than this pushes neither way
TOP_K = 5  # features compared by the top-k overlap
CACHE_SIZE = 256
GLOBAL_TTL_SECONDS = 600

Method = Literal["shap", "lime", "lrp", "dice", "shap_recent", "lrp_recent"]
Direction = Literal["raises", "lowers", "neutral"]


# --- the report's shape (the API returns it as JSON) -----------------------------------------


class MethodStatus(BaseModel):
    method: Method
    ok: bool
    detail: str | None = None  # why it is missing, when it is


class MatrixRow(BaseModel):
    """One factor in the XAI matrix, for the focus prediction."""

    name: str
    label: str
    meaning: str
    value: float
    display: str
    shap: float | None  # change in P(correct)
    lime: float | None  # change in the local surrogate's P(correct)
    lrp: float | None  # relevance, in log-odds
    direction: Direction
    consistent: bool | None  # every method that ran pushes the same way (None: under two ran)
    recent_shap: float | None  # mean SHAP for this factor over the recent predictions


class AgreementPair(BaseModel):
    pair: str  # e.g. "shap~lime"
    spearman: float
    top_k_overlap: float
    verdict: str


class DiceQuality(BaseModel):
    requested: int
    found: int
    validity: float
    proximity: float | None
    sparsity: float | None
    diversity: float | None


class Quality(BaseModel):
    shap_additivity_error: float | None  # |base + sum - prediction|; 0 = complete
    lrp_conservation_error: float | None
    lime_r2: float | None
    dice: DiceQuality | None


class WaterfallStep(BaseModel):
    name: str
    label: str
    display: str
    value: float


class Waterfall(BaseModel):
    base: float
    output: float
    steps: list[WaterfallStep]  # strongest first


class PredictionColumn(BaseModel):
    """One recent prediction: the question's concept, when, and how it turned out."""

    concept: str
    at: datetime
    correct: bool
    p_correct: float


class DecisionPlot(BaseModel):
    base: float
    features: list[str]  # most important on average first
    labels: list[str]
    predictions: list[PredictionColumn]
    contributions: list[list[float]]  # per prediction, SHAP in `features` order


class Heatmap(BaseModel):
    unit: str
    features: list[str]
    labels: list[str]
    predictions: list[PredictionColumn]
    values: list[list[float]]  # per feature (rows) x prediction (columns), LRP relevance


class CounterfactualOption(BaseModel):
    p_correct: float
    values: list[str]
    changed: list[bool]


class CounterfactualTable(BaseModel):
    direction: Literal["higher", "lower"]  # which way the counterfactuals move the prediction
    features: list[str]
    labels: list[str]
    now: list[str]
    p_now: float
    options: list[CounterfactualOption]


class RadarAxis(BaseModel):
    key: str
    label: str
    value: float  # 0..1
    detail: str


class Radar(BaseModel):
    traits: list[RadarAxis]
    clusters: list[RadarAxis]


class Focus(BaseModel):
    recommendation_id: UUID | None  # None: an answered question with no recommendation
    concept_id: str
    concept: str
    at: datetime
    p_correct: float
    answered_correctly: bool | None


class UserReport(BaseModel):
    generated_at: datetime
    model: ModelSummary
    disclaimer: str
    summary: str
    focus: Focus | None
    matrix: list[MatrixRow]
    agreement: list[AgreementPair]
    quality: Quality
    waterfall: Waterfall | None
    decision: DecisionPlot | None
    heatmap: Heatmap | None
    counterfactuals: CounterfactualTable | None
    radar: Radar
    recent_predictions: int
    methods: list[MethodStatus]


# --- helpers ------------------------------------------------------------------------------------

T = TypeVar("T")


def _run(method: Method, fn: Callable[[], T], status: list[MethodStatus]) -> T | None:
    """Run one explanation method; a failure is recorded, not raised, so the rest still renders."""
    try:
        result = fn()
    except Exception as err:  # noqa: BLE001 (any failure: the report must still render)
        logger.exception("xai: %s failed", method)
        status.append(MethodStatus(method=method, ok=False, detail=type(err).__name__))
        return None
    status.append(MethodStatus(method=method, ok=True))
    return result


def _sign(v: float | None) -> int:
    return 0 if v is None or abs(v) < NEAR_ZERO else (1 if v > 0 else -1)


def _matrix(
    x: np.ndarray,
    shap: explain.Attribution | None,
    lime: explain.Attribution | None,
    lrp: explain.Attribution | None,
    recent_shap: np.ndarray | None,
) -> list[MatrixRow]:
    rows = []
    for j, f in enumerate(FEATURES):
        values = {
            "shap": None if shap is None else float(shap.values[j]),
            "lime": None if lime is None else float(lime.values[j]),
            "lrp": None if lrp is None else float(lrp.values[j]),
        }
        signs = {s for s in map(_sign, values.values()) if s != 0}
        lead = next((v for v in values.values() if _sign(v) != 0), None)
        ran = sum(v is not None for v in values.values())
        rows.append(
            MatrixRow(
                name=f.name,
                label=f.label,
                meaning=MEANINGS[f.name],
                value=float(x[j]),
                display=display(f.name, float(x[j])),
                direction="neutral" if lead is None else ("raises" if lead > 0 else "lowers"),
                consistent=None if ran < 2 else len(signs) <= 1,
                recent_shap=None if recent_shap is None else float(recent_shap[j]),
                **values,
            )
        )

    def strength(row: MatrixRow) -> float:
        for v in (row.shap, row.lime, row.lrp):
            if v is not None:
                return abs(v)
        return 0.0

    return sorted(rows, key=strength, reverse=True)


def _counterfactual_table(
    x: np.ndarray, p_now: float, found: list[explain.Counterfactual]
) -> CounterfactualTable:
    actionable = [j for j, f in enumerate(FEATURES) if f.actionable]
    return CounterfactualTable(
        direction="higher" if p_now < explain.DECISION else "lower",
        features=[FEATURE_NAMES[j] for j in actionable],
        labels=[FEATURES[j].label for j in actionable],
        now=[display(FEATURE_NAMES[j], float(x[j])) for j in actionable],
        p_now=p_now,
        options=[
            CounterfactualOption(
                p_correct=cf.p_correct,
                values=[display(FEATURE_NAMES[j], float(cf.x[j])) for j in actionable],
                changed=[bool(abs(cf.x[j] - x[j]) > 1e-6) for j in actionable],
            )
            for cf in found
        ],
    )


def _radar(learner_model: LearnerModel, graph: GraphSnapshot, user_id: UUID) -> Radar:
    state = learner_model.get_state(user_id)
    traits = [
        RadarAxis(
            key=name,
            label=TRAIT_LABELS.get(name, name),
            value=float(t.mean),
            detail=f"{t.mean:.2f} ± {math.sqrt(t.variance):.2f}",
        )
        for name in TRAIT_LABELS
        if (t := state.traits.traits.get(name)) is not None
    ]
    known = {c: s.p_mastery for c, s in state.mastery.items() if s.n_attempts > 0}
    effective = bkt.effective_mastery(graph, known)
    by_cluster: dict[str, list[str]] = {}
    for concept_id in graph.concept_ids:
        by_cluster.setdefault(graph.get_concept(concept_id).cluster, []).append(concept_id)
    clusters = [
        RadarAxis(
            key=cluster,
            label=CLUSTER_LABELS.get(cluster, cluster),
            value=float(np.mean([effective[c] for c in ids])),
            detail=f"{sum(c in known for c in ids)} of {len(ids)} concepts started",
        )
        for cluster, ids in by_cluster.items()
    ]
    return Radar(traits=traits, clusters=clusters)


def _focus(session: Session, graph: GraphSnapshot, user_id: UUID, rows: list):
    """The prediction the report centres on: the latest recommended question (with the model's
    inputs as they were when it was recommended), or, if the learner has no recommendation, their
    latest answered question. Returns (recommendation id, concept, at, inputs, answered) or None."""
    rec = session.scalars(
        select(m.RecommendationRow)
        .outerjoin(m.AttemptRow, m.AttemptRow.recommendation_id == m.RecommendationRow.id)
        .where(m.RecommendationRow.user_id == user_id, m.RecommendationRow.item_id.is_not(None))
        # newest first; at the same moment, the question still waiting for an answer
        .order_by(m.RecommendationRow.created_at.desc(), m.AttemptRow.id.is_(None).desc())
        .limit(1)
    ).first()
    if rec is not None:
        try:
            item = graph.get_item(rec.item_id)
        except KeyError:
            item = None  # withdrawn from the bank since
        if item is not None:
            state, _ = replay(session, graph, user_id, until=rec.created_at)
            answered = session.scalar(
                select(m.AttemptRow.correct).where(m.AttemptRow.recommendation_id == rec.id)
            )
            concept = graph.get_concept(item.concept_id)
            return rec.id, concept, rec.created_at, state.features(item, rec.created_at), answered
    if not rows:
        return None
    last = rows[-1]
    attempt = session.get(m.AttemptRow, last.attempt_id)
    concept = graph.get_concept(graph.get_item(attempt.item_id).concept_id)
    return attempt.recommendation_id, concept, attempt.created_at, last.x, bool(last.y)


def _columns(
    session: Session, graph: GraphSnapshot, rows: list, model: PerformanceModel
) -> list[PredictionColumn]:
    attempts = {
        a.id: a
        for a in session.scalars(
            select(m.AttemptRow).where(m.AttemptRow.id.in_([r.attempt_id for r in rows]))
        )
    }
    p = model.predict_proba(np.array([r.x for r in rows]))
    columns = []
    for row, p_row in zip(rows, p, strict=True):
        attempt = attempts[row.attempt_id]
        try:
            concept = graph.get_concept(graph.get_item(attempt.item_id).concept_id).name
        except KeyError:
            concept = attempt.item_id
        columns.append(
            PredictionColumn(
                concept=concept, at=attempt.created_at, correct=bool(row.y), p_correct=float(p_row)
            )
        )
    return columns


# --- the entry point ------------------------------------------------------------------------------

_cache: OrderedDict[tuple, UserReport] = OrderedDict()
_cache_lock = threading.Lock()


def _cache_key(session: Session, user_id: UUID, model: PerformanceModel) -> tuple:
    n, last = session.execute(
        select(func.count(), func.max(m.AttemptRow.created_at)).where(
            m.AttemptRow.user_id == user_id
        )
    ).one()
    rec = session.scalar(
        select(func.max(m.RecommendationRow.created_at)).where(
            m.RecommendationRow.user_id == user_id
        )
    )
    return (user_id, n, last, rec, model.card.get("trained_at"))


def explain_user(
    session: Session,
    graph: GraphSnapshot,
    learner_model: LearnerModel,
    user_id: UUID,
    model: PerformanceModel | None = None,
) -> UserReport:
    """The Explainability section of one learner's report: the XAI matrix, method agreement,
    explanation quality, a plain-language summary, and the data behind every chart."""
    model = model or load()
    key = _cache_key(session, user_id, model)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]

    status: list[MethodStatus] = []
    _, rows = replay(session, graph, user_id)
    focus = _focus(session, graph, user_id, rows)
    recent = rows[-RECENT:]

    # the person level: SHAP for every recent prediction in one call, LRP for each (cheap)
    shap_recent = lrp_recent = columns = None
    if recent:
        xs = np.array([r.x for r in recent])
        shap_recent = _run("shap_recent", lambda: explain.shap_values(model, xs), status)
        lrp_recent = _run(
            "lrp_recent",
            lambda: np.array([explain.lrp_attribution(model, x).values for x in xs]),
            status,
        )
        columns = _columns(session, graph, recent, model)

    # the focus prediction, each method on its own
    shap = lime = lrp = found = None
    focus_out = waterfall = cf_table = None
    if focus is not None:
        rec_id, concept, at, x, answered = focus
        p_now = float(model.predict_proba(x)[0])
        shap = _run("shap", lambda: explain.shap_attribution(model, x), status)
        lime = _run("lime", lambda: explain.lime_attribution(model, x), status)
        lrp = _run("lrp", lambda: explain.lrp_attribution(model, x), status)
        found = _run("dice", lambda: explain.counterfactuals(model, x, total=DICE_TOTAL), status)
        focus_out = Focus(
            recommendation_id=rec_id,
            concept_id=concept.id,
            concept=concept.name,
            at=at,
            p_correct=p_now,
            answered_correctly=answered,
        )
        if shap is not None:
            order = np.argsort(-np.abs(shap.values))
            waterfall = Waterfall(
                base=shap.base,
                output=shap.output,
                steps=[
                    WaterfallStep(
                        name=FEATURE_NAMES[j],
                        label=FEATURES[j].label,
                        display=display(FEATURE_NAMES[j], float(x[j])),
                        value=float(shap.values[j]),
                    )
                    for j in order
                ],
            )
        if found is not None:
            cf_table = _counterfactual_table(x, p_now, found)

    recent_mean = None if shap_recent is None else shap_recent[0].mean(axis=0)
    matrix = _matrix(focus[3], shap, lime, lrp, recent_mean) if focus is not None else []

    # agreement between the methods that ran on the focus prediction
    values = {a.method: a.values for a in (shap, lime, lrp) if a is not None}
    agreement = [
        AgreementPair(
            pair=pair, spearman=rho, top_k_overlap=overlap, verdict=metrics.agreement_word(rho)
        )
        for pair, rho, overlap in metrics.agreement(values, TOP_K)
    ]

    dice_q = None
    if focus is not None and found is not None:
        dice_q = DiceQuality(
            **metrics.dice_quality(
                focus[3],
                focus_out.p_correct,
                found,
                DICE_TOTAL,
                explain.mad_scale(model.background),
            )
        )
    quality = Quality(
        shap_additivity_error=None if shap is None else abs(shap.residual),
        lrp_conservation_error=None if lrp is None else abs(lrp.residual),
        lime_r2=None if lime is None else lime.fidelity,
        dice=dice_q,
    )

    # person-level charts, features ordered by how much they mattered on average
    decision = heatmap = None
    importance = (
        np.abs(shap_recent[0]).mean(axis=0)
        if shap_recent is not None
        else (np.abs(lrp_recent).mean(axis=0) if lrp_recent is not None else None)
    )
    if importance is not None and columns:
        order = [int(j) for j in np.argsort(-importance)]
        names = [FEATURE_NAMES[j] for j in order]
        labels = [LABELS[n] for n in names]
        if shap_recent is not None:
            values_r, base_r = shap_recent
            decision = DecisionPlot(
                base=base_r,
                features=names,
                labels=labels,
                predictions=columns,
                contributions=[[float(row[j]) for j in order] for row in values_r],
            )
        if lrp_recent is not None:
            heatmap = Heatmap(
                unit="logit (log-odds)",
                features=names,
                labels=labels,
                predictions=columns,
                values=[[float(lrp_recent[i, j]) for i in range(len(columns))] for j in order],
            )

    # the plain-language paragraph, from the same numbers
    top = [
        (row.label, "raised" if row.direction == "raises" else "lowered")
        for row in matrix
        if row.direction != "neutral"
    ][:3]
    lead_pair = next(
        (a for a in agreement if a.pair == "shap~lime"), agreement[0] if agreement else None
    )
    agreement_text = (
        None
        if lead_pair is None
        else (
            " and ".join(p.upper() for p in lead_pair.pair.split("~")),
            lead_pair.verdict,
            lead_pair.spearman,
        )
    )
    cf_text = cf_direction = None
    if cf_table is not None and cf_table.options:
        first = cf_table.options[0]
        changes = [
            f"{label.lower()} {now} → {then}"
            for label, now, then, changed in zip(
                cf_table.labels, cf_table.now, first.values, first.changed, strict=True
            )
            if changed
        ]
        cf_text = "; ".join(changes) + f" (predicted {round(first.p_correct * 100)}%)"
        cf_direction = "above" if cf_table.direction == "higher" else "below"
    recent_top = None
    if recent_mean is not None:
        recent_top = LABELS[FEATURE_NAMES[int(np.argmax(np.abs(shap_recent[0]).mean(axis=0)))]]
    summary = summary_paragraph(
        concept=None if focus_out is None else focus_out.concept,
        p_correct=None if focus_out is None else focus_out.p_correct,
        top=top,
        agreement=agreement_text,
        recent_top=recent_top,
        n_recent=len(recent),
        counterfactual=cf_text,
        counterfactual_direction=cf_direction,
    )

    report = UserReport(
        generated_at=datetime.now(UTC),
        model=model_summary(model),
        disclaimer=DISCLAIMER,
        summary=summary,
        focus=focus_out,
        matrix=matrix,
        agreement=agreement,
        quality=quality,
        waterfall=waterfall,
        decision=decision,
        heatmap=heatmap,
        counterfactuals=cf_table,
        radar=_radar(learner_model, graph, user_id),
        recent_predictions=len(recent),
        methods=status,
    )
    with _cache_lock:
        _cache[key] = report
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return report


# --- the cross-learner view (admins only) -------------------------------------------------------


class GlobalPoint(BaseModel):
    shap: float
    position: float  # the feature's value, 0 = its lowest plausible value, 1 = its highest


class GlobalFeature(BaseModel):
    name: str
    label: str
    mean_abs_shap: float
    points: list[GlobalPoint]


class GlobalAttributions(BaseModel):
    """SHAP for recent predictions across learners, for a beeswarm. No learner is identified."""

    generated_at: datetime
    learners: int
    predictions: int
    base: float | None
    features: list[GlobalFeature]


_global: tuple[float, GlobalAttributions] | None = None
_global_lock = threading.Lock()


def global_attributions(
    session: Session,
    graph: GraphSnapshot,
    model: PerformanceModel | None = None,
    max_learners: int = 60,
    per_learner: int = 8,
) -> GlobalAttributions:
    global _global
    with _global_lock:
        if _global is not None and time.monotonic() - _global[0] < GLOBAL_TTL_SECONDS:
            return _global[1]
    model = model or load()
    recent_learners = session.scalars(
        select(m.AttemptRow.user_id)
        .join(m.User, m.User.id == m.AttemptRow.user_id)
        .where(m.User.is_admin.is_(False), m.User.deleted_at.is_(None))
        .group_by(m.AttemptRow.user_id)
        .order_by(func.max(m.AttemptRow.created_at).desc())
        .limit(max_learners)
    ).all()
    xs = [
        row.x
        for user_id in recent_learners
        for row in replay(session, graph, user_id)[1][-per_learner:]
    ]
    features: list[GlobalFeature] = []
    base = None
    if xs:
        values, base = explain.shap_values(model, np.array(xs))
        low = np.array([f.low for f in FEATURES], dtype=float)
        high = np.array([f.high for f in FEATURES], dtype=float)
        positions = np.clip((np.array(xs) - low) / (high - low), 0, 1)
        features = sorted(
            (
                GlobalFeature(
                    name=f.name,
                    label=f.label,
                    mean_abs_shap=float(np.abs(values[:, j]).mean()),
                    points=[
                        GlobalPoint(shap=float(values[i, j]), position=float(positions[i, j]))
                        for i in range(len(xs))
                    ],
                )
                for j, f in enumerate(FEATURES)
            ),
            key=lambda g: g.mean_abs_shap,
            reverse=True,
        )
    result = GlobalAttributions(
        generated_at=datetime.now(UTC),
        learners=len(recent_learners),
        predictions=len(xs),
        base=base,
        features=features,
    )
    with _global_lock:
        _global = (time.monotonic(), result)
    return result


def warm_up() -> None:
    """Import and exercise the explainers once, so the first report is not slow (importing `shap`
    and `lime` alone takes seconds). Called in a background thread at start-up."""
    started = time.monotonic()
    try:
        model = load()
        explain.shap_values(model, model.background[:1])
        explain.lime_attribution(model, model.background[0])
    except Exception:  # noqa: BLE001 (warming is best effort)
        logger.exception("xai: warm-up failed")
        return
    logger.info("xai: explainers warm in %.1f s", time.monotonic() - started)
