"""Pre-registered analyses H1, H2, H4 and questionnaire reliability (docs/EVALUATION_PLAN.md).

Every function takes the exported Frames and returns plain numbers, so the report generator and
the tests can use them directly. Confidence intervals are learner-level (cluster) bootstraps or
learner-clustered GEE, because answers from the same learner are not independent.
"""

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy.stats import rankdata

from analysis.export import Frames
from app.psychometrics.questionnaire import QuestionnaireItem
from app.psychometrics.reliability import alpha_per_trait

H1_FEATURES = [
    "clarity_c",
    "clarity_missing",
    "log_dwell",
    "expanded",
    "replays",
    "dismissed",
    "followup_signed",
]
EPS = 1e-4


# --- metrics -----------------------------------------------------------------------------------


def auc(y: np.ndarray, score: np.ndarray) -> float:
    """Area under the ROC curve via the rank-sum (Mann-Whitney) formula, ties averaged."""
    y = np.asarray(y, dtype=bool)
    n_pos, n_neg = y.sum(), (~y).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = rankdata(score)
    return float((ranks[y].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def cluster_bootstrap(
    groups: np.ndarray, stat, n_boot: int = 1000, seed: int = 0
) -> tuple[float, float]:
    """95% percentile CI of stat(index_array) when resampling whole groups (learners)."""
    rng = np.random.default_rng(seed)
    unique = np.unique(groups)
    members = {g: np.flatnonzero(groups == g) for g in unique}
    values = []
    for _ in range(n_boot):
        picked = rng.choice(unique, size=len(unique), replace=True)
        idx = np.concatenate([members[g] for g in picked])
        value = stat(idx)
        if np.isfinite(value):
            values.append(value)
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


# --- H1: do explanation-interaction features improve next-answer prediction? -------------------


def h1_dataset(frames: Frames) -> pd.DataFrame:
    """Practice attempts that have an earlier explanation (with feedback) on the same concept;
    features come from the most recent such explanation."""
    attempts = frames.attempts
    practice = attempts[
        attempts.test_phase.isna() & ~attempts.is_microcheck & attempts.p_hat.notna()
    ].copy()
    expl = frames.explanations[frames.explanations.has_feedback].copy()
    if practice.empty or expl.empty:
        return pd.DataFrame()
    practice = practice.sort_values("created_at")
    expl = expl.rename(columns={"explanation_id": "prior_explanation_id"}).sort_values("created_at")
    merged = pd.merge_asof(
        practice,
        expl,
        on="created_at",
        by=["learner", "concept_id"],
        direction="backward",
        allow_exact_matches=False,  # the explanation must come strictly before the answer
    )
    merged = merged[merged.prior_explanation_id.notna()].copy()
    p = merged.p_hat.astype(float).clip(EPS, 1 - EPS)
    merged["logit_p"] = np.log(p / (1 - p))
    clarity = merged.clarity.astype(float)
    merged["clarity_c"] = (clarity - 3).fillna(0.0)
    merged["clarity_missing"] = clarity.isna().astype(float)
    merged["log_dwell"] = np.log1p(merged.dwell_ms.astype(float).fillna(0.0) / 1000)
    merged["expanded"] = merged.expanded.fillna(False).astype(float)
    merged["replays"] = merged.replays.fillna(0).astype(float)
    merged["dismissed"] = merged.dismissed.fillna(False).astype(float)
    merged["followup_signed"] = merged.followup_correct.map({True: 1.0, False: -1.0}).fillna(0.0)
    merged["y"] = merged.correct.astype(float)
    return merged.reset_index(drop=True)


def _fit_predict(train: pd.DataFrame, test: pd.DataFrame, columns: list[str]) -> np.ndarray:
    usable = [c for c in columns if train[c].std() > 0]  # constant columns are unidentifiable
    X_train = sm.add_constant(train[usable], has_constant="add")
    X_test = sm.add_constant(test[usable], has_constant="add")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = sm.Logit(train.y, X_train).fit(disp=0, method="lbfgs", maxiter=500)
    return np.asarray(model.predict(X_test))


def h1(frames: Frames, folds: int = 5, seed: int = 0, n_boot: int = 1000) -> dict:
    data = h1_dataset(frames)
    if data.empty or data.learner.nunique() < folds:
        return {"available": False, "n": len(data)}
    rng = np.random.default_rng(seed)
    learners = data.learner.unique()
    fold_of = dict(zip(rng.permutation(learners), np.arange(len(learners)) % folds, strict=True))
    data["fold"] = data.learner.map(fold_of)
    base_pred = np.zeros(len(data))
    full_pred = np.zeros(len(data))
    for k in range(folds):
        train, test = data[data.fold != k], data[data.fold == k]
        base_pred[test.index] = _fit_predict(train, test, ["logit_p"])
        full_pred[test.index] = _fit_predict(train, test, ["logit_p", *H1_FEATURES])
    y = data.y.to_numpy()
    groups = data.learner.to_numpy()
    return {
        "available": True,
        "n": len(data),
        "learners": int(data.learner.nunique()),
        "auc_base": auc(y, base_pred),
        "auc_full": auc(y, full_pred),
        "logloss_base": log_loss(y, base_pred),
        "logloss_full": log_loss(y, full_pred),
        "auc_gain_ci": cluster_bootstrap(
            groups, lambda i: auc(y[i], full_pred[i]) - auc(y[i], base_pred[i]), n_boot, seed
        ),
        "logloss_gain_ci": cluster_bootstrap(
            groups,
            lambda i: log_loss(y[i], base_pred[i]) - log_loss(y[i], full_pred[i]),
            n_boot,
            seed,
        ),
    }


# --- H2: does the arm change micro-check accuracy? ---------------------------------------------


def h2(frames: Frames) -> dict:
    expl = frames.explanations[frames.explanations.followup_correct.notna()]
    data = expl.merge(frames.learners, on="learner").merge(
        frames.attempts[["concept_id", "cluster"]].drop_duplicates(), on="concept_id", how="left"
    )
    rates = data.groupby("arm").followup_correct.agg(["mean", "count"]).to_dict("index")
    if data.arm.nunique() < 2 or "generic" not in set(data.arm):
        return {"available": False, "rates": rates}
    data = data.assign(y=data.followup_correct.astype(float))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = smf.gee(
            "y ~ C(arm, Treatment('generic')) + C(cluster)",
            groups="learner",
            data=data,
            family=sm.families.Binomial(),
            cov_struct=sm.cov_struct.Exchangeable(),
        ).fit()
    effects = {}
    conf = fit.conf_int()
    for name in fit.params.index:
        if name.startswith("C(arm"):
            arm = name.split("[T.")[1].rstrip("]")
            effects[arm] = {
                "odds_ratio": float(np.exp(fit.params[name])),
                "ci": (float(np.exp(conf.loc[name, 0])), float(np.exp(conf.loc[name, 1]))),
                "p": float(fit.pvalues[name]),
            }
    return {"available": True, "rates": rates, "effects": effects, "n": len(data)}


# --- H4: normalised learning gain ---------------------------------------------------------------


def h4(frames: Frames, n_boot: int = 2000, seed: int = 0) -> dict:
    tests = frames.attempts[frames.attempts.test_phase.notna()]
    if tests.empty:
        return {"available": False}
    scores = tests.pivot_table(
        index="learner", columns="test_phase", values="correct", aggfunc="mean"
    )
    if not {"pretest", "posttest"} <= set(scores.columns):
        return {"available": False}
    scores = scores.dropna().join(frames.learners.set_index("learner"))
    scores = scores[scores.pretest < 1]  # gain is undefined at a perfect pre-test
    scores["gain"] = (scores.posttest - scores.pretest) / (1 - scores.pretest)
    rng = np.random.default_rng(seed)
    per_arm = {}
    for arm, group in scores.groupby("arm"):
        g = group.gain.to_numpy()
        boots = [rng.choice(g, len(g)).mean() for _ in range(n_boot)]
        per_arm[arm] = {
            "n": len(g),
            "mean": float(g.mean()),
            "ci": (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))),
        }
    diffs = {}
    if "generic" in per_arm:
        base = scores[scores.arm == "generic"].gain.to_numpy()
        for arm in per_arm:
            if arm == "generic":
                continue
            other = scores[scores.arm == arm].gain.to_numpy()
            boots = [
                rng.choice(other, len(other)).mean() - rng.choice(base, len(base)).mean()
                for _ in range(n_boot)
            ]
            diffs[arm] = {
                "diff": float(other.mean() - base.mean()),
                "ci": (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))),
                "cohens_d": float(
                    (other.mean() - base.mean())
                    / np.sqrt((other.var(ddof=1) + base.var(ddof=1)) / 2)
                ),
            }
    return {"available": True, "per_arm": per_arm, "vs_generic": diffs}


# --- reliability ---------------------------------------------------------------------------------


def reliability(frames: Frames, items: list[QuestionnaireItem]) -> dict[str, tuple[float, int]]:
    responses: dict[str, dict[str, int]] = {}
    for row in frames.questionnaire.itertuples():
        responses.setdefault(row.learner, {})[row.item_id] = int(row.value)
    return alpha_per_trait(items, responses)


# --- XAI measures (docs/XAI_DESIGN.md §5) -------------------------------------------------------


def xai(frames: Frames, n_boot: int = 1000, seed: int = 0) -> dict:
    """Per arm: rationale and counterfactual coverage of recommendations, how often learners open
    "Why this?" per explanation shown, and the share of 1-tap ratings that say it was helpful
    (learner-level bootstrap CI). Faithfulness itself is checked in CI (tests/test_rationale.py)."""
    recs = frames.recommendations.merge(frames.learners, on="learner")
    if recs.empty:
        return {"available": False}
    shown = frames.explanations.merge(frames.learners, on="learner")
    events = frames.xai_events.merge(frames.learners, on="learner")
    per_arm = {}
    for arm, group in recs.groupby("arm"):
        arm_shown = shown[shown.arm == arm]
        arm_events = events[events.arm == arm]
        opened = arm_events[arm_events.type == "why_opened"].explanation_id.nunique()
        ratings = arm_events[arm_events.type == "why_rated"].dropna(subset=["helpful"])
        row = {
            "recommendations": len(group),
            "with_rationale": float(group.has_rationale.mean()),
            "with_counterfactual": float((group.n_counterfactuals > 0).mean()),
            "explanations_shown": len(arm_shown),
            "why_open_rate": opened / len(arm_shown) if len(arm_shown) else float("nan"),
            "ratings": len(ratings),
            "helpful_share": float(ratings.helpful.astype(bool).mean())
            if len(ratings)
            else float("nan"),
            "helpful_ci": (float("nan"), float("nan")),
        }
        if len(ratings) >= 2 and ratings.learner.nunique() >= 2:
            helpful = ratings.helpful.astype(float).to_numpy()
            row["helpful_ci"] = cluster_bootstrap(
                ratings.learner.to_numpy(), lambda i, h=helpful: float(h[i].mean()), n_boot, seed
            )
        per_arm[arm] = row
    return {"available": True, "per_arm": per_arm, "rules": recs.rule.value_counts().to_dict()}
