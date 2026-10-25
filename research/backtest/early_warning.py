"""H5 backtest: do drift and resonance alarms come *before* a learner starts struggling?
(docs/MODEL_SPEC.md §6, the deck's Phase-2 claim). Offline only; nothing here runs live.

Struggle run: two wrong answers in a row on the same concept (the planner's struggle rule, the
Phase-1 "score < 0.70" moment). For each detector, the alarm "before attempt i" uses only
information available before attempt i. The deck claims prediction *before performance declines*,
so a run is warned early only if an alarm switched on within `window` answers up to and including
the run's FIRST wrong answer; lead = answers between that alarm onset and the first wrong answer.

Detectors:
- naive baseline: the previous answer (any concept) was wrong.
- drift: CUSUM over residuals r = correct - p_hat; alarm while S > h.
- resonance: geometric mean of P (last clarity on the concept), C (p_hat), B (consistency of the
  last 5 answers) and T (time efficiency); alarm while R < threshold.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from analysis.export import Frames


@dataclass(frozen=True)
class BacktestConfig:
    window: int = 5
    cusum_k: float = 0.1
    cusum_h: float = 1.0
    resonance_threshold: float = 0.6  # top of the deck's "potential struggle" band


def _sequences(frames: Frames) -> dict[str, pd.DataFrame]:
    a = frames.attempts
    a = a[a.test_phase.isna() & a.p_hat.notna()].sort_values("created_at")
    return {learner: g.reset_index(drop=True) for learner, g in a.groupby("learner")}


def failure_events(seq: pd.DataFrame) -> list[tuple[int, int]]:
    """(first wrong, second wrong) answer indices of every struggle run: two wrong answers in a
    row on the same concept (other concepts may be answered in between)."""
    events, last_wrong = [], {}  # concept -> index of an unbroken wrong answer
    for i, row in enumerate(seq.itertuples()):
        if row.correct:
            last_wrong.pop(row.concept_id, None)
        elif row.concept_id in last_wrong and last_wrong[row.concept_id] is not None:
            events.append((last_wrong[row.concept_id], i))
            last_wrong[row.concept_id] = None  # one event per run
        elif row.concept_id not in last_wrong:
            last_wrong[row.concept_id] = i
    return events


def naive_alarms(seq: pd.DataFrame, cfg: BacktestConfig) -> np.ndarray:
    alarms = np.zeros(len(seq), dtype=bool)
    alarms[1:] = ~seq.correct.to_numpy()[:-1]
    return alarms


def drift_alarms(seq: pd.DataFrame, cfg: BacktestConfig) -> np.ndarray:
    residual = seq.correct.astype(float).to_numpy() - seq.p_hat.astype(float).to_numpy()
    alarms = np.zeros(len(seq), dtype=bool)
    s = 0.0
    for i, r in enumerate(residual):
        alarms[i] = s > cfg.cusum_h  # state before attempt i
        s = max(0.0, s - r - cfg.cusum_k)
    return alarms


def resonance_scores(seq: pd.DataFrame, explanations: pd.DataFrame | None = None) -> np.ndarray:
    """R before each attempt (geometric mean of P, C, B, T; MODEL_SPEC §6)."""
    clarity_by_concept: dict[str, list[tuple[object, float]]] = {}
    if explanations is not None and not explanations.empty:
        rated = explanations[explanations.clarity.notna()]
        for row in rated.itertuples():
            clarity_by_concept.setdefault(row.concept_id, []).append(
                (row.created_at, (float(row.clarity) - 1) / 4)
            )
    scores = np.zeros(len(seq))
    correct = seq.correct.astype(float).to_numpy()
    latency = seq.latency_ms.astype(float).to_numpy()
    for i, row in enumerate(seq.itertuples()):
        recent = correct[max(0, i - 5) : i]
        b = 1 - 4 * recent.var() if len(recent) >= 2 else 0.75
        t = float(np.clip(np.median(latency[:i]) / latency[i - 1], 0, 1)) if i >= 2 else 0.75
        prior_ratings = [
            v for when, v in clarity_by_concept.get(row.concept_id, []) if when < row.created_at
        ]
        p = prior_ratings[-1] if prior_ratings else 0.5
        parts = np.clip([p, float(row.p_hat), b, t], 1e-3, 1)
        scores[i] = float(np.exp(np.mean(np.log(parts))))
    return scores


def evaluate(
    alarm_lists: list[np.ndarray], event_lists: list[list[tuple[int, int]]], window: int
) -> dict:
    """Early-warning metrics. An alarm *onset* is an attempt where the alarm switches on. A run
    (first wrong t0, second wrong t1) is warned early if an onset lies in [t0 - window, t0]."""
    detected, leads, true_onsets, n_onsets, attempts = 0, [], 0, 0, 0
    n_events = sum(len(e) for e in event_lists)
    for alarms, events in zip(alarm_lists, event_lists, strict=True):
        attempts += len(alarms)
        onsets = [i for i in range(len(alarms)) if alarms[i] and (i == 0 or not alarms[i - 1])]
        n_onsets += len(onsets)
        for t0, _t1 in events:
            warned = [j for j in onsets if t0 - window <= j <= t0]
            if warned:
                detected += 1
                leads.append(t0 - warned[-1])
        true_onsets += sum(any(j <= t0 <= j + window for t0, _ in events) for j in onsets)
    return {
        "events": n_events,
        "recall": detected / n_events if n_events else float("nan"),
        "precision": true_onsets / n_onsets if n_onsets else float("nan"),
        "median_lead": float(np.median(leads)) if leads else float("nan"),
        "alarms_per_100": 100 * n_onsets / attempts if attempts else float("nan"),
    }


def backtest(frames: Frames, cfg: BacktestConfig | None = None) -> dict[str, dict]:
    cfg = cfg or BacktestConfig()
    seqs = _sequences(frames)
    events = [failure_events(s) for s in seqs.values()]
    results = {}
    for name, detector in (
        ("naive (last answer wrong)", naive_alarms),
        ("drift (CUSUM)", drift_alarms),
    ):
        results[name] = evaluate([detector(s, cfg) for s in seqs.values()], events, cfg.window)
    resonance = []
    for learner, seq in seqs.items():
        expl = frames.explanations[frames.explanations.learner == learner]
        resonance.append(resonance_scores(seq, expl) < cfg.resonance_threshold)
    results[f"resonance (R < {cfg.resonance_threshold})"] = evaluate(resonance, events, cfg.window)
    return results
