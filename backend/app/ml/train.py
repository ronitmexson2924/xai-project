"""Train the performance model, compare it with BKT and logistic regression, and write the model
artifact (app/ml/artifacts/performance_model.json) and research/reports/performance_model.md.

    cd backend && PYTHONPATH=../research python -m app.ml.train                 # simulated data
    cd backend && python -m app.ml.train --source db                            # study data

`--source simulated` runs the R6 simulator (synthetic learners through the real learner model and
planner) inside a transaction that is rolled back. `--source db` uses every consented learner's
logged attempts. Learners are split 70/15/15 into training, validation and test sets, so the test
metrics are on learners the model has never seen. Seeded: the same data gives the same model.
"""

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.graph.service import GraphSnapshot
from app.ml import explain
from app.ml.features import FEATURE_NAMES, FEATURES, dataset
from app.ml.model import ARTIFACT, PerformanceModel

SEED = 0
# model selection: every combination is fitted on the training learners and the one with the
# lowest log loss on the validation learners is kept (the test learners are never looked at)
HIDDEN_GRID = ((32, 16), (16, 8), (8,))
ALPHA_GRID = (1e-3, 1e-2, 1e-1, 1.0)
BACKGROUND_SIZE = 200
REPORT = Path(__file__).resolve().parents[3] / "research" / "reports" / "performance_model.md"


def expected_calibration_error(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    index = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    return float(
        sum(
            abs(y[index == b].mean() - p[index == b].mean()) * (index == b).mean()
            for b in range(bins)
            if (index == b).any()
        )
    )


def metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return {
        "auc": float(roc_auc_score(y, p)),
        "log_loss": float(log_loss(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "accuracy": float(((p >= 0.5) == y).mean()),
        "ece": expected_calibration_error(y, p),
    }


def split_by_learner(groups: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, ...]:
    learners = rng.permutation(np.unique(groups))
    n = len(learners)
    train, val = learners[: int(0.7 * n)], learners[int(0.7 * n) : int(0.85 * n)]
    return np.isin(groups, train), np.isin(groups, val), ~np.isin(groups, np.r_[train, val])


def fit(
    x: np.ndarray, y: np.ndarray, groups: np.ndarray, p_bkt: np.ndarray, source: str
) -> tuple[PerformanceModel, dict]:
    rng = np.random.default_rng(SEED)
    train, val, test = split_by_learner(groups, rng)
    mean = x[train].mean(axis=0)
    scale = np.where(x[train].std(axis=0) > 1e-9, x[train].std(axis=0), 1.0)
    z = (x - mean) / scale

    def network(hidden: tuple[int, ...], alpha: float) -> MLPClassifier:
        return MLPClassifier(
            hidden_layer_sizes=hidden,
            activation="relu",
            alpha=alpha,
            learning_rate_init=1e-3,
            max_iter=400,
            early_stopping=True,  # stops on a 15% share of the training learners' answers
            n_iter_no_change=20,
            random_state=SEED,
        ).fit(z[train], y[train])

    selection = []
    best: tuple[float, MLPClassifier] | None = None
    for hidden in HIDDEN_GRID:
        for alpha in ALPHA_GRID:
            candidate = network(hidden, alpha)
            score = float(log_loss(y[val], candidate.predict_proba(z[val])[:, 1]))
            selection.append({"hidden": list(hidden), "alpha": alpha, "val_log_loss": score})
            if best is None or score < best[0]:
                best = (score, candidate)
    assert best is not None
    net = best[1]
    hidden = tuple(int(w.shape[1]) for w in net.coefs_[:-1])
    logistic = LogisticRegression(max_iter=1000).fit(z[train], y[train])

    background = x[train][rng.choice(train.sum(), min(BACKGROUND_SIZE, train.sum()), replace=False)]
    model = PerformanceModel(
        mean=mean,
        scale=scale,
        weights=[w.copy() for w in net.coefs_],
        biases=[b.copy() for b in net.intercepts_],
        background=background,
    )
    assert np.allclose(model.predict_proba(x[test]), net.predict_proba(z[test])[:, 1], atol=1e-6)

    results = {
        "neural network (this model)": metrics(y[test], model.predict_proba(x[test])),
        "logistic regression": metrics(y[test], logistic.predict_proba(z[test])[:, 1]),
        "BKT (the learner model)": metrics(y[test], p_bkt[test]),
        "always the base rate": metrics(y[test], np.full(test.sum(), y[train].mean())),
    }

    # global explanations: mean |SHAP| and the methods' agreement on a sample of test learners
    sample = x[test][rng.choice(test.sum(), min(120, test.sum()), replace=False)]
    per_row = [explain.explain(model, row) for row in sample]
    shap_abs = np.mean([np.abs(e.attributions["shap"].values) for e in per_row], axis=0)
    lrp_abs = np.mean([np.abs(e.attributions["lrp"].values) for e in per_row], axis=0)
    lime_fit = [e.attributions["lime"].fidelity for e in per_row]
    agreement = {k: float(np.mean([e.agreement[k] for e in per_row])) for k in per_row[0].agreement}
    cf_found = np.mean([len(e.counterfactuals) > 0 for e in per_row])
    cf_valid = np.mean(
        [(cf.p_correct >= 0.5) != (e.p_correct >= 0.5) for e in per_row for cf in e.counterfactuals]
        or [1.0]
    )
    cf_sparsity = np.mean([len(cf.changes) for e in per_row for cf in e.counterfactuals] or [0])

    # faithfulness (deletion test): replacing the top-3 SHAP features by the reference mean should
    # move the prediction more than replacing 3 random features
    moved_top, moved_random = [], []
    reference = model.background.mean(axis=0)
    for e in per_row:
        top = np.argsort(-np.abs(e.attributions["shap"].values))[:3]
        rand = rng.choice(len(FEATURE_NAMES), 3, replace=False)
        for idx, store in ((top, moved_top), (rand, moved_random)):
            changed = e.x.copy()
            changed[idx] = reference[idx]
            store.append(abs(float(model.predict_proba(changed)[0]) - e.p_correct))

    card = {
        "name": "Performance model",
        "task": "P(the learner answers this question correctly), from what the system knew just "
        "before the answer",
        "architecture": f"multilayer perceptron, {len(FEATURE_NAMES)} inputs -> "
        + " -> ".join(str(h) for h in hidden)
        + " (ReLU) -> 1 (sigmoid)",
        "trained_on": source,
        "trained_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "rows": {"train": int(train.sum()), "validation": int(val.sum()), "test": int(test.sum())},
        "learners": {
            "train": int(len(np.unique(groups[train]))),
            "validation": int(len(np.unique(groups[val]))),
            "test": int(len(np.unique(groups[test]))),
        },
        "base_rate": float(y.mean()),
        "model_selection": {
            "chosen": {"hidden": list(hidden), "alpha": float(net.alpha)},
            "candidates": selection,
        },
        "test_metrics": results,
        "global_importance": {
            "shap": dict(zip(FEATURE_NAMES, map(float, shap_abs), strict=True)),
            "lrp": dict(zip(FEATURE_NAMES, map(float, lrp_abs), strict=True)),
        },
        "explanation_quality": {
            "rows_explained": len(per_row),
            "method_agreement_spearman": agreement,
            "lime_median_r2": float(np.median(lime_fit)),
            "counterfactual_found": float(cf_found),
            "counterfactual_valid": float(cf_valid),
            "counterfactual_mean_features_changed": float(cf_sparsity),
            "deletion_top3_shap": float(np.mean(moved_top)),
            "deletion_random3": float(np.mean(moved_random)),
        },
        "features": [
            {"name": f.name, "label": f.label, "actionable": f.actionable} for f in FEATURES
        ],
        "limitations": [
            "Trained on simulated learners until the pilot provides real answers: retrain with "
            "--source db and compare."
            if source.startswith("simulated")
            else "Trained on the study's own learners: small samples make the metrics uncertain.",
            "It predicts; it does not decide. The planner's choices do not use it (the study's "
            "pre-registered design), so its explanations describe this prediction only.",
            "Feature attributions describe the model, not causes in the learner.",
        ],
    }
    return PerformanceModel(**{**model.__dict__, "card": card}), card


def simulated_learners(session: Session, learners_per_arm: int, steps: int) -> list[UUID]:
    from simulator.driver import RunConfig, simulate  # research/ on PYTHONPATH

    simulate(session, RunConfig(learners_per_arm=learners_per_arm, steps=steps, seed=11))
    return list(
        session.scalars(select(m.User.id).where(m.User.email.like("%@sim")).order_by(m.User.id))
    )


def study_learners(session: Session) -> list[UUID]:
    return list(
        session.scalars(
            select(m.User.id)
            .where(m.User.consent_at.is_not(None), m.User.is_admin.is_(False))
            .order_by(m.User.id)
        )
    )


def write_report(card: dict, path: Path = REPORT) -> None:
    rows = "\n".join(
        f"| {name} | {r['auc']:.3f} | {r['log_loss']:.3f} | {r['brier']:.3f} | {r['accuracy']:.3f} "
        f"| {r['ece']:.3f} |"
        for name, r in card["test_metrics"].items()
    )
    labels = {f["name"]: f["label"] for f in card["features"]}
    shap_imp = card["global_importance"]["shap"]
    imp = "\n".join(
        f"| {labels[n]} | {v:.4f} | {card['global_importance']['lrp'][n]:.3f} |"
        for n, v in sorted(shap_imp.items(), key=lambda kv: -kv[1])
    )
    q = card["explanation_quality"]
    agree = ", ".join(f"{k} {v:.2f}" for k, v in q["method_agreement_spearman"].items())
    path.write_text(
        f"""# Performance model: training report

Generated by `python -m app.ml.train` on {card["trained_at"]}; do not edit by hand.

**Task.** {card["task"]}.
**Model.** {card["architecture"]}. **Data.** {card["trained_on"]}:
{card["rows"]["train"]} / {card["rows"]["validation"]} / {card["rows"]["test"]} answers from
{card["learners"]["train"]} / {card["learners"]["validation"]} / {card["learners"]["test"]}
learners (train / validation / test, split by learner). Base rate of correct answers:
{card["base_rate"]:.2f}.

**Model selection.** {len(card["model_selection"]["candidates"])} candidate networks (hidden
layers × L2 strength) were fitted on the training learners. The one with the lowest log loss on
the validation learners was kept: hidden layers {card["model_selection"]["chosen"]["hidden"]},
L2 {card["model_selection"]["chosen"]["alpha"]:g}. Test learners were used only for the table
below.

## Test metrics (learners the model never saw)

| Model | AUC ↑ | Log loss ↓ | Brier ↓ | Accuracy ↑ | ECE ↓ |
|---|---|---|---|---|---|
{rows}

## What drives its predictions (global)

Mean absolute SHAP value (change in P(correct)) and mean absolute LRP relevance (logit), over
{q["rows_explained"]} test answers.

| Feature | mean abs SHAP | mean abs LRP |
|---|---|---|
{imp}

## Quality of the explanations

- Agreement between methods (Spearman rank correlation, mean): {agree}.
- LIME's local surrogate: median R² {q["lime_median_r2"]:.2f}.
- Counterfactuals (DiCE): found for {q["counterfactual_found"]:.0%} of answers;
  {q["counterfactual_valid"]:.0%} actually flip the prediction; on average
  {q["counterfactual_mean_features_changed"]:.1f} features changed.
- Faithfulness (deletion test): replacing the 3 features SHAP ranks highest by their reference
  value moves P(correct) by {q["deletion_top3_shap"]:.3f} on average, against
  {q["deletion_random3"]:.3f} for 3 random features.

## Limitations

{chr(10).join("- " + item for item in card["limitations"])}
"""
    )


def build_dataset(args: argparse.Namespace) -> tuple[np.ndarray, ...]:
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        if args.source == "simulated":
            users = simulated_learners(session, args.learners_per_arm, args.steps)
            source = f"simulated learners (R6 simulator, {len(users)} learners, {args.steps} steps)"
        else:
            users = study_learners(session)
            source = f"study data ({len(users)} consented learners)"
        graph = GraphSnapshot.from_db(session, include_drafts=True)
        x, y, p_bkt, groups = dataset(session, graph, users)
        session.rollback()  # the simulation leaves nothing behind
    return x, y, p_bkt, groups, source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", choices=["simulated", "db"], default="simulated")
    parser.add_argument("--learners-per-arm", type=int, default=60)
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument(
        "--cache", type=Path, help="save the dataset here, or reuse it if the file exists"
    )
    args = parser.parse_args(argv)

    started = time.perf_counter()
    if args.cache and args.cache.exists():
        saved = np.load(args.cache, allow_pickle=False)
        x, y, p_bkt, groups = saved["x"], saved["y"], saved["p_bkt"], saved["groups"]
        source = str(saved["source"])
    else:
        x, y, p_bkt, groups, source = build_dataset(args)
        if args.cache:
            np.savez_compressed(args.cache, x=x, y=y, p_bkt=p_bkt, groups=groups, source=source)
    if len(np.unique(groups)) < 10 or len(np.unique(y)) < 2:
        print(f"not enough data to train ({len(y)} answers from {len(np.unique(groups))} learners)")
        return 1
    model, card = fit(x, y, groups, p_bkt, source)
    model.save(ARTIFACT)
    write_report(card)
    nn = card["test_metrics"]["neural network (this model)"]
    took = time.perf_counter() - started
    print(f"trained on {len(y)} answers in {took:.0f}s; test AUC {nn['auc']:.3f}")
    print(f"wrote {ARTIFACT} and {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
