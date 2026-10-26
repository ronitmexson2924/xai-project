"""Post-hoc explanations of one performance-model prediction, four ways.

- SHAP (Lundberg & Lee, 2017), `shap` library, permutation algorithm: each feature's additive
  contribution to P(correct) relative to the average prediction on the reference sample.
- LIME (Ribeiro et al., 2016), `lime` library: a weighted linear surrogate fitted on perturbed
  copies of the input; reports its local fit (R²) so a poor surrogate is visible.
- LRP (Bach et al., 2015), epsilon rule, implemented here on the network's own weights: how the
  output logit is redistributed back onto the inputs, layer by layer.
- DiCE (Mothilal et al., 2020), implemented here: a small, diverse set of counterfactuals, i.e.
  realistic changes to actionable features that would flip the prediction. It minimises DiCE's
  loss (hinge validity + MAD-weighted proximity - DPP diversity) by gradient descent on this
  network, then applies DiCE's post-hoc sparsity step. (The `dice-ml` package would add ~430 MB
  of unused GPU and boosting libraries.)

Every method explains the same model on the same input, and `agreement` reports how far they
concur, so a disagreement between methods is shown rather than hidden.
"""

from dataclasses import dataclass, field

import numpy as np

from app.ml.features import FEATURE_NAMES, FEATURES, N_FEATURES
from app.ml.model import PerformanceModel

SEED = 7
LIME_SAMPLES = 2000
SHAP_MAX_EVALS = 2 * N_FEATURES * 20 + 1  # 20 antithetic permutations
LRP_EPSILON = 1e-2
DECISION = 0.5  # counterfactuals flip the prediction across this probability


@dataclass(frozen=True)
class Attribution:
    """Per-feature contributions from one method (same feature order as FEATURE_NAMES)."""

    method: str
    unit: str  # what the numbers are in
    values: np.ndarray
    base: float  # the reference the contributions are relative to
    output: float  # the model output being explained, in `unit`
    fidelity: float | None = None  # LIME: R² of the local surrogate
    residual: float = 0.0  # base + sum(values) - output: 0 means the attribution is complete


@dataclass(frozen=True)
class Counterfactual:
    x: np.ndarray
    p_correct: float
    changes: dict[str, tuple[float, float]]  # feature -> (now, counterfactual)


@dataclass(frozen=True)
class Explanation:
    x: np.ndarray
    p_correct: float
    attributions: dict[str, Attribution]
    counterfactuals: list[Counterfactual]
    agreement: dict[str, float]  # "shap~lime" -> Spearman rank correlation of the attributions
    notes: list[str] = field(default_factory=list)


# --- SHAP -----------------------------------------------------------------------------------


def shap_attribution(model: PerformanceModel, x: np.ndarray) -> Attribution:
    import shap  # imported on first use: it adds over a second to the API's start-up

    masker = shap.maskers.Independent(model.background, max_samples=len(model.background))
    explainer = shap.PermutationExplainer(model.predict_proba, masker, seed=SEED)
    result = explainer(np.atleast_2d(x), max_evals=SHAP_MAX_EVALS, silent=True)
    values = np.asarray(result.values[0], dtype=float)
    base = float(np.ravel(result.base_values)[0])
    output = float(model.predict_proba(x)[0])
    return Attribution(
        "shap", "probability", values, base, output, residual=base + values.sum() - output
    )


# --- LIME -----------------------------------------------------------------------------------


def lime_attribution(model: PerformanceModel, x: np.ndarray) -> Attribution:
    from lime.lime_tabular import LimeTabularExplainer  # first use only, like shap

    explainer = LimeTabularExplainer(
        model.background,
        feature_names=list(FEATURE_NAMES),
        class_names=["wrong", "correct"],
        mode="classification",
        discretize_continuous=False,  # keep a linear model on the features themselves
        sample_around_instance=True,
        random_state=SEED,
    )

    def proba(rows: np.ndarray) -> np.ndarray:
        p = model.predict_proba(rows)
        return np.column_stack([1 - p, p])

    exp = explainer.explain_instance(
        np.asarray(x, dtype=float),
        proba,
        num_features=N_FEATURES,
        num_samples=LIME_SAMPLES,
        labels=(1,),
    )
    # LIME fits on standardised features: a feature's local contribution relative to the
    # training mean is its weight times its standardised value
    weights = np.zeros(N_FEATURES)
    for index, weight in exp.as_map()[1]:
        weights[index] = weight
    scaled = (np.asarray(x) - explainer.scaler.mean_) / explainer.scaler.scale_
    values = weights * scaled
    base = float(exp.intercept[1])
    local = float(np.ravel(exp.local_pred)[0])
    return Attribution(
        "lime",
        "probability (local linear surrogate)",
        values,
        base,
        local,
        fidelity=float(exp.score),
        residual=base + values.sum() - local,
    )


# --- LRP ------------------------------------------------------------------------------------


def lrp_attribution(
    model: PerformanceModel, x: np.ndarray, eps: float = LRP_EPSILON
) -> Attribution:
    """Epsilon-rule LRP from the output logit to the standardised inputs. The input z0 = 0 is the
    training-mean learner, so relevance is relative to an average learner. Biases absorb some
    relevance; `residual` reports what the inputs do not account for."""
    acts = model.activations(x)
    relevance = acts[-1][0].copy()  # the logit
    absorbed = 0.0
    for i in range(len(model.weights) - 1, -1, -1):
        a = acts[i][0]
        w, b = model.weights[i], model.biases[i]
        z = a @ w + b
        denom = z + eps * np.where(z >= 0, 1.0, -1.0)
        s = relevance / denom
        absorbed += float(np.sum(b * s))
        relevance = a * (s @ w.T)
    output = float(acts[-1][0, 0])
    return Attribution(
        "lrp",
        "logit (log-odds)",
        relevance,
        absorbed,
        output,
        residual=absorbed + relevance.sum() - output,
    )


# --- DiCE -----------------------------------------------------------------------------------


def _mad(background: np.ndarray) -> np.ndarray:
    mad = np.median(np.abs(background - np.median(background, axis=0)), axis=0)
    spread = background.std(axis=0)
    return np.where(mad > 1e-6, mad, np.where(spread > 1e-6, spread, 1.0))


def counterfactuals(
    model: PerformanceModel,
    x: np.ndarray,
    total: int = 3,
    proximity_weight: float = 0.5,
    diversity_weight: float = 1.0,
    steps: int = 400,
    lr: float = 0.05,
) -> list[Counterfactual]:
    """DiCE: `total` diverse counterfactuals that move only actionable features within their
    plausible ranges (and never reduce the number of questions answered)."""
    x = np.asarray(x, dtype=float)
    p_now = float(model.predict_proba(x)[0])
    want_correct = p_now < DECISION
    sign = 1.0 if want_correct else -1.0
    margin = 0.5  # in logit units past the decision boundary (DiCE's hinge margin)
    mad = _mad(model.background)
    low = np.array([f.low for f in FEATURES], dtype=float)
    high = np.array([f.high for f in FEATURES], dtype=float)
    attempts = FEATURE_NAMES.index("attempts")
    low[attempts] = x[attempts]  # practice cannot be undone
    misconception = FEATURE_NAMES.index("misconception")
    high[misconception] = x[misconception]  # a misconception can be cleared, never advised
    mask = np.array([f.actionable for f in FEATURES], dtype=float)
    rng = np.random.default_rng(SEED)
    cfs = x + mask * rng.normal(0, 0.3, (total, N_FEATURES)) * mad
    cfs = np.clip(cfs, low, high)

    def dpp(points: np.ndarray) -> float:
        d = np.abs(points[:, None, :] - points[None, :, :]) / mad
        return float(np.linalg.det(1.0 / (1.0 + d.sum(-1) / N_FEATURES)))

    m1, m2 = np.zeros_like(cfs), np.zeros_like(cfs)
    for step in range(1, steps + 1):
        grad = np.zeros_like(cfs)
        for k in range(total):
            logit = float(model.logit(cfs[k])[0])
            if sign * logit < margin:  # hinge validity loss: max(0, margin - sign * logit)
                grad[k] -= sign * model.grad_logit(cfs[k]) / total
            grad[k] += proximity_weight * np.sign(cfs[k] - x) / mad / (total * N_FEATURES)
        if total > 1 and diversity_weight > 0:  # numerical gradient of the DPP diversity term
            base = dpp(cfs)
            for k in range(total):
                for j in np.flatnonzero(mask):
                    bumped = cfs.copy()
                    bumped[k, j] += 1e-4 * mad[j]
                    grad[k, j] -= diversity_weight * (dpp(bumped) - base) / (1e-4 * mad[j])
        grad *= mask
        m1 = 0.9 * m1 + 0.1 * grad  # Adam
        m2 = 0.999 * m2 + 0.001 * grad**2
        update = (m1 / (1 - 0.9**step)) / (np.sqrt(m2 / (1 - 0.999**step)) + 1e-8)
        cfs = np.clip(cfs - lr * update * mad, low, high)

    def valid(c: np.ndarray) -> bool:
        p = float(model.predict_proba(c)[0])
        return p >= DECISION if want_correct else p < DECISION

    def tidy(c: np.ndarray) -> np.ndarray:
        c = c.copy()
        for j, f in enumerate(FEATURES):
            if f.integer:
                c[j] = np.round(c[j])
        prereq_mean, prereq_min = (
            FEATURE_NAMES.index("prereq_mean"),
            FEATURE_NAMES.index("prereq_min"),
        )
        c[prereq_min] = min(c[prereq_min], c[prereq_mean])  # the weakest is never above the mean
        return np.clip(c, low, high)

    found: list[Counterfactual] = []
    for c in cfs:
        c = tidy(c)
        if not valid(c):
            continue
        # DiCE's post-hoc sparsity: undo the smallest changes while the prediction stays flipped
        order = np.argsort(np.abs(c - x) / mad)
        for j in order:
            if c[j] != x[j]:
                trial = c.copy()
                trial[j] = x[j]
                if valid(trial):
                    c = trial
        changes = {
            FEATURE_NAMES[j]: (float(x[j]), float(c[j]))
            for j in range(N_FEATURES)
            if abs(c[j] - x[j]) > 1e-6
        }
        if changes and all(changes != cf.changes for cf in found):
            found.append(Counterfactual(c, float(model.predict_proba(c)[0]), changes))
    return found


# --- all together ---------------------------------------------------------------------------


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    if ra.std() == 0 or rb.std() == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def explain(model: PerformanceModel, x: np.ndarray) -> Explanation:
    x = np.asarray(x, dtype=float)
    attributions = {
        "shap": shap_attribution(model, x),
        "lime": lime_attribution(model, x),
        "lrp": lrp_attribution(model, x),
    }
    names = list(attributions)
    agreement = {
        f"{a}~{b}": _spearman(attributions[a].values, attributions[b].values)
        for i, a in enumerate(names)
        for b in names[i + 1 :]
    }
    notes = []
    lime = attributions["lime"]
    if lime.fidelity is not None and lime.fidelity < 0.5:
        notes.append(
            f"LIME's local linear surrogate fits poorly here (R² = {lime.fidelity:.2f}): "
            "trust SHAP and LRP more for this prediction."
        )
    if min(agreement.values()) < 0.3:
        notes.append("The methods disagree on what matters most for this prediction.")
    return Explanation(
        x=x,
        p_correct=float(model.predict_proba(x)[0]),
        attributions=attributions,
        counterfactuals=counterfactuals(model, x),
        agreement=agreement,
        notes=notes,
    )
