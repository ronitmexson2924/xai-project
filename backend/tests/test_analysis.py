"""R8: the analysis pipeline (research/analysis, research/backtest) on known and simulated data."""

import numpy as np
import pandas as pd
import pytest
from analysis import hypotheses as h
from analysis.export import load_frames, pseudonym
from backtest.early_warning import BacktestConfig, backtest, drift_alarms, evaluate, failure_events
from sqlalchemy.orm import Session

from app.graph.service import GraphSnapshot
from simulator.driver import RunConfig, simulate


def test_auc_and_log_loss() -> None:
    y = np.array([0, 0, 1, 1])
    assert h.auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert h.auc(y, np.array([0.9, 0.8, 0.2, 0.1])) == 0.0
    assert h.auc(y, np.full(4, 0.5)) == 0.5
    assert h.log_loss(np.array([1, 0]), np.array([0.5, 0.5])) == pytest.approx(np.log(2))


def test_pseudonyms_are_stable_and_salted() -> None:
    assert pseudonym("u1", "s") == pseudonym("u1", "s")
    assert pseudonym("u1", "s") != pseudonym("u1", "t")
    assert len(pseudonym("u1", "s")) == 12


def _seq(rows: list[tuple[str, bool]], p_hat: float = 0.7) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "concept_id": [c for c, _ in rows],
            "correct": [ok for _, ok in rows],
            "p_hat": p_hat,
            "latency_ms": 10_000,
        }
    )


def test_struggle_runs_need_two_wrong_in_a_row_on_one_concept() -> None:
    seq = _seq([("a", False), ("b", True), ("a", False), ("a", False), ("a", True), ("a", False)])
    # a wrong at 0, b in between, a wrong at 2 -> run (0, 2); index 3 continues the same run
    assert failure_events(seq) == [(0, 2)]


def test_early_warning_metrics() -> None:
    alarms = np.array([False, True, True, False, False, False, False, False])
    events = [(3, 4)]  # first wrong at 3: the alarm started at 1, two answers earlier
    r = evaluate([alarms], [events], window=5)
    assert r["recall"] == 1.0 and r["median_lead"] == 2.0 and r["precision"] == 1.0
    late = evaluate([np.roll(alarms, 4)], [events], window=5)  # alarm starts after t0
    assert late["recall"] == 0.0 and late["precision"] == 0.0


def test_drift_alarm_fires_after_sustained_underperformance() -> None:
    seq = _seq([("a", False)] * 6, p_hat=0.8)  # residual -0.8 each: S grows by 0.7 per answer
    alarms = drift_alarms(seq, BacktestConfig())
    assert not alarms[:2].any() and alarms[2:].all()


def test_pipeline_end_to_end_on_simulated_logs(db: Session) -> None:
    simulate(db, RunConfig(learners_per_arm=2, steps=8, seed=3))
    graph = GraphSnapshot.from_db(db, include_drafts=True)
    frames = load_frames(db, graph, salt="test", email_like="%@sim")

    assert sorted(frames.learners.arm.value_counts()) == [2, 2, 2]
    practice = frames.attempts[frames.attempts.test_phase.isna()]
    assert practice.p_hat.notna().all()  # recovered from the live model's audit log
    assert set(frames.attempts.test_phase.dropna()) == {"pretest", "posttest"}
    assert frames.explanations.has_feedback.all()
    assert not frames.learners.learner.str.contains("@").any()

    assert h.h1(frames, folds=3, n_boot=20)["available"]
    r2 = h.h2(frames)
    assert set(r2["rates"]) == {"generic", "static_personalized", "closed_loop"}
    r4 = h.h4(frames, n_boot=50)
    assert r4["available"] and set(r4["vs_generic"]) == {"static_personalized", "closed_loop"}
    assert set(backtest(frames)) and all(r["events"] >= 0 for r in backtest(frames).values())

    rx = h.xai(frames, n_boot=20)
    assert rx["available"] and set(rx["per_arm"]) == {
        "generic",
        "static_personalized",
        "closed_loop",
    }
    assert all(r["with_rationale"] == 1.0 for r in rx["per_arm"].values())  # every decision
    assert all(r["with_counterfactual"] > 0 for r in rx["per_arm"].values())
