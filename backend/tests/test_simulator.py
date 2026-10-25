"""R6: smoke test of the simulator (research/simulator) against the real services."""

from sqlalchemy.orm import Session

from simulator import metrics
from simulator.driver import ARMS, RunConfig, simulate
from simulator.population import ResponseConfig


def test_simulator_runs_all_arms_paired(db: Session) -> None:
    cfg = RunConfig(
        learners_per_arm=2, steps=4, seed=7, response=ResponseConfig(self_report_gap=0.2)
    )
    records, meta = simulate(db, cfg)

    assert len(records) == len(ARMS) * 2 * 4
    assert set(meta["final_estimates"]) == {(arm, i) for arm in ARMS for i in range(2)}
    starts = {arm: metrics.recovery_curve(records, arm)[0] for arm in ARMS}
    assert len(set(starts.values())) == 1  # same learners and questionnaire answers in every arm
    assert {r.source for r in records if r.arm == "generic"} == {"generic"}
    assert {r.source for r in records if r.arm == "static_personalized"} == {"trait_mapped"}
    for arm in ARMS:
        summary = metrics.arm_summary(records, meta, arm)
        assert 0 <= summary["style_mae"] <= 1 and summary["regret_per_step"] >= 0
