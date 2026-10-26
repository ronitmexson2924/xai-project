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


def _frames(attempts: list[dict], explanations: list[dict], learners: list[str]) -> "h.Frames":
    from analysis.export import Frames

    return Frames(
        learners=pd.DataFrame({"learner": learners, "arm": "generic"}),
        attempts=pd.DataFrame(attempts),
        explanations=pd.DataFrame(explanations),
        questionnaire=pd.DataFrame(columns=["learner", "item_id", "value"]),
    )


def _attempt(learner: str, minute: int, **kw) -> dict:
    t0 = pd.Timestamp("2026-01-01", tz="UTC")
    return {
        "learner": learner,
        "concept_id": "c",
        "created_at": t0 + pd.Timedelta(minutes=minute),
        "correct": kw.get("correct", True),
        "p_hat": 0.6,
        "is_microcheck": kw.get("is_microcheck", False),
        "test_phase": kw.get("test_phase"),
    }


def test_learners_with_fewer_than_five_practice_answers_are_excluded() -> None:
    attempts = [_attempt("a", i) for i in range(5)]
    attempts += [_attempt("b", i) for i in range(4)]
    attempts += [_attempt("b", 10 + i, is_microcheck=True) for i in range(3)]  # not practice
    attempts += [_attempt("b", 20, test_phase="pretest")]  # not practice either
    frames = _frames(attempts, [], ["a", "b"])
    core, excluded = h.exclude_sparse(frames)
    assert excluded == ["b"]
    assert set(core.learners.learner) == {"a"} and set(core.attempts.learner) == {"a"}
    assert set(frames.learners.learner) == {"a", "b"}  # the original frames are untouched


def test_h1_ignores_feedback_that_was_final_only_after_the_answer() -> None:
    t0 = pd.Timestamp("2026-01-01", tz="UTC")
    expl = {
        "learner": "a",
        "explanation_id": "e1",
        "concept_id": "c",
        "created_at": t0,  # shown before the answer at minute 5...
        "has_feedback": True,
        "dwell_ms": 30_000,
        "expanded": True,
        "replays": 0,
        "clarity": 4,
        "followup_correct": True,
        "dismissed": False,
    }
    answer = [_attempt("a", 5)]
    late = _frames(answer, [{**expl, "feedback_at": t0 + pd.Timedelta(minutes=9)}], ["a"])
    assert h.h1_dataset(late).empty  # ...but its summary was only final at minute 9
    early = _frames(answer, [{**expl, "feedback_at": t0 + pd.Timedelta(minutes=2)}], ["a"])
    data = h.h1_dataset(early)
    assert len(data) == 1 and data.prior_explanation_id[0] == "e1"
    unknown = _frames(answer, [{**expl, "feedback_at": None}], ["a"])
    assert h.h1_dataset(unknown).empty  # no timestamp: never assume it was available
