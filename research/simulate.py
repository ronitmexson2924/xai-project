"""Run the R6 simulation study and regenerate research/reports/simulation.md (+ figures).

    cd backend && PYTHONPATH=../research python ../research/simulate.py           # ~15-20 min
    cd backend && PYTHONPATH=../research python ../research/simulate.py --quick   # ~1 min

Needs a migrated Postgres (DATABASE_URL, as for the backend). Every study runs inside a
transaction that is rolled back, so nothing is left in the database. Seeded: same output each run.
"""

import argparse
import time
from dataclasses import dataclass, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from simulator import metrics  # noqa: E402
from simulator.driver import ARMS, RunConfig, simulate  # noqa: E402
from simulator.population import ResponseConfig  # noqa: E402

REPORT_DIR = Path(__file__).parent / "reports"
LABEL = {"generic": "generic", "static_personalized": "static", "closed_loop": "closed loop"}
GAP = 0.2  # self-report gap in the main world
ACCURATE = ResponseConfig(self_report_gap=0.0)
GAPPED = ResponseConfig(self_report_gap=GAP)


@dataclass(frozen=True)
class Plan:
    main_gap: RunConfig
    main_accurate: RunConfig
    behaviour_on: RunConfig
    long: RunConfig
    null: RunConfig
    sweep_base: RunConfig
    sweep_eps: tuple[float, ...] = (0.0, 0.05, 0.1)
    sweep_var: tuple[float, ...] = (0.04, 0.09)


def plan(quick: bool) -> Plan:
    n, steps, n_small = (6, 20, 4) if quick else (40, 60, 24)
    main = RunConfig(learners_per_arm=n, steps=steps, seed=1, response=GAPPED)
    closed = ("closed_loop",)
    return Plan(
        main_gap=main,
        main_accurate=replace(main, response=ACCURATE),
        behaviour_on=replace(main, arms=closed, behaviour_alpha=0.05),
        long=replace(main, arms=closed, learners_per_arm=n_small, steps=int(steps * 2.5), seed=4),
        null=replace(
            main, arms=("static_personalized", "closed_loop"), null_preferences=True, seed=2
        ),
        sweep_base=replace(main, arms=closed, learners_per_arm=n_small, seed=3),
    )


def run(cfg: RunConfig):
    with SessionLocal() as session:
        try:
            return simulate(session, cfg)
        finally:
            session.rollback()


def f3(x: float) -> str:
    return f"{x:.3f}"


def arm_table(summaries: dict[str, dict[str, float]]) -> list[str]:
    rows = [
        ("style-trait error, start (questionnaire)", "questionnaire_mae", f3),
        ("style-trait error, end", "style_mae", f3),
        ("persistence + self-efficacy error, end", "behaviour_mae", f3),
        ("regret per explanation", "regret_per_step", f3),
        ("micro-check accuracy", "followup_accuracy", f3),
        ("learning gain (share of concepts known)", "learning_gain", f3),
        ("distinct styles shown per learner", "distinct_styles", lambda x: f"{x:.1f}"),
    ]
    lines = ["| metric | " + " | ".join(LABEL[a] for a in ARMS) + " |", "|---|---|---|---|"]
    for label, key, fmt in rows:
        lines.append(f"| {label} | " + " | ".join(fmt(summaries[a][key]) for a in ARMS) + " |")
    return lines


def ci(d: tuple[float, float, float]) -> str:
    return f"{d[0]:+.3f} (95% CI {d[1]:+.3f} to {d[2]:+.3f})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--out", type=Path, default=REPORT_DIR)
    args = parser.parse_args()
    p = plan(args.quick)
    started = time.perf_counter()
    (args.out / "figures").mkdir(parents=True, exist_ok=True)

    studies = {}
    for name in ("main_gap", "main_accurate", "behaviour_on", "long", "null"):
        print(f"{name} ...", flush=True)
        studies[name] = run(getattr(p, name))
    sweep = []
    for eps in p.sweep_eps:
        for var in p.sweep_var:
            r, m = run(replace(p.sweep_base, epsilon=eps, questionnaire_variance=var))
            s = metrics.arm_summary(r, m, "closed_loop")
            sweep.append((eps, var, s))
            print(f"  sweep eps={eps} var={var}: error {s['style_mae']:.3f}", flush=True)

    summary = {
        world: {arm: metrics.arm_summary(*studies[world], arm) for arm in ARMS}
        for world in ("main_gap", "main_accurate")
    }
    gains = {arm: metrics.learning_gain(*studies["main_gap"], arm) for arm in ARMS}
    behaviour_on = metrics.arm_summary(*studies["behaviour_on"], "closed_loop")
    null = {arm: metrics.false_preference_share(studies["null"][1], arm) for arm in p.null.arms}
    long_curve = metrics.recovery_curve(studies["long"][0], "closed_loop")
    long_regret = np.diff(metrics.cumulative_regret(studies["long"][0], "closed_loop"))

    # --- figures ----------------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for world, style in (("main_gap", "-"), ("main_accurate", ":")):
        tag = f"gap {GAP}" if world == "main_gap" else "accurate self-report"
        for arm, colour in (("static_personalized", "tab:orange"), ("closed_loop", "tab:blue")):
            curve = metrics.recovery_curve(studies[world][0], arm)
            ax.plot(curve, style, color=colour, label=f"{LABEL[arm]}, {tag}")
    ax.plot(long_curve, "--", color="grey", label=f"closed loop, gap {GAP}, long run")
    ax.set_xlabel("explanations shown")
    ax.set_ylabel("mean |estimated − true| (style traits)")
    ax.set_title("Style-trait recovery")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(args.out / "figures" / "trait_recovery.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for arm in ARMS:
        ax.plot(metrics.cumulative_regret(studies["main_gap"][0], arm), label=LABEL[arm])
    ax.set_xlabel("explanations shown")
    ax.set_ylabel("cumulative regret (true style fit)")
    ax.set_title(f"Cost of not showing each learner's best style (self-report gap {GAP})")
    ax.legend()
    fig.tight_layout()
    fig.savefig(args.out / "figures" / "regret.png", dpi=120)
    plt.close(fig)

    # --- report -----------------------------------------------------------------------------------
    g, a = summary["main_gap"], summary["main_accurate"]
    closed_g, static_g = g["closed_loop"], g["static_personalized"]
    reduction = 1 - closed_g["style_mae"] / closed_g["questionnaire_mae"]
    half = len(long_regret) // 2
    best = min(sweep, key=lambda row: row[2]["regret_per_step"])
    n, steps = p.main_gap.learners_per_arm, p.main_gap.steps
    gain_vs_static = metrics.paired_difference(gains["closed_loop"], gains["static_personalized"])
    gain_vs_generic = metrics.paired_difference(gains["closed_loop"], gains["generic"])
    elapsed = (time.perf_counter() - started) / 60

    lines = [
        "# Simulation study (R6, hypothesis H3)",
        "",
        f"> Generated by `research/simulate.py{' --quick' if args.quick else ''}` in "
        f"{elapsed:.1f} min. **Do not edit by hand**: rerun the script. The interpretation and "
        "the design decisions taken from it are in `tasks/ronit.md` (R6) and `docs/MODEL_SPEC.md`.",
        "",
        "## Setup",
        "",
        f"- {n} synthetic learners per arm, with **the same learners and questionnaire answers "
        f"in every arm** (paired), {steps} explanations each. Real `LearnerModel` + `Planner` on "
        "Postgres; the fake explainer stands in for Module B.",
        "- True traits ~ Beta(2, 2). Learners answer the questionnaire from their *self-view*: "
        "true trait + N(0, gap), plus item noise. Two worlds:",
        f"  - **gap {GAP}** (main): self-report only partly matches what actually helps. This is "
        "the case the closed loop exists for.",
        "  - **accurate self-report** (gap 0): the questionnaire already tells the truth.",
        "- The response model uses the bandit's own functional form (a well-specified world). A "
        "better-fitting style makes an explanation more likely to teach the concept, raises the "
        "clarity rating (asked on 1 in 3) and lowers quick dismissals. Micro-checks are answered "
        f"{p.main_gap.microcheck_rate:.0%} of the time. Learners quit sessions after wrong answers "
        "(more often with low persistence) and sometimes rate their confidence.",
        "",
        "## Key numbers",
        "",
        "- With a self-report gap, the closed loop cuts style-trait error from "
        f"{f3(closed_g['questionnaire_mae'])} to {f3(closed_g['style_mae'])} "
        f"(**{reduction:.0%} lower**) in {steps} explanations. Static stays at "
        f"{f3(static_g['style_mae'])}.",
        "- With accurate self-report it barely moves: "
        f"{f3(a['closed_loop']['questionnaire_mae'])} → {f3(a['closed_loop']['style_mae'])}.",
        f"- Over {steps} explanations, regret per explanation is "
        f"{f3(closed_g['regret_per_step'])} (closed loop) vs {f3(static_g['regret_per_step'])} "
        f"(static) and {f3(g['generic']['regret_per_step'])} (generic). In the long run "
        f"({len(long_curve)} explanations), the closed loop's regret per explanation is "
        f"{f3(float(np.mean(long_regret[:half])))} in the first half and "
        f"{f3(float(np.mean(long_regret[half:])))} in the second.",
        f"- Learning gain, closed loop − static (paired): {ci(gain_vs_static)}; "
        f"closed loop − generic: {ci(gain_vs_generic)}.",
        "- Behavioural-trait EWMA (rate 0.05) moves persistence/self-efficacy error from "
        f"{f3(closed_g['behaviour_mae'])} (off) to {f3(behaviour_on['behaviour_mae'])} (on).",
        f"- Lowest-regret setting in the sweep: ε = {best[0]}, questionnaire variance = {best[1]}.",
        "",
        f"## 1. Three arms, self-report gap {GAP} (main)",
        "",
        *arm_table(g),
        "",
        "## 2. Three arms, accurate self-report",
        "",
        *arm_table(a),
        "",
        "## 3. Trait recovery and regret over time",
        "",
        "![Style-trait recovery](figures/trait_recovery.png)",
        "",
        f"Long run ({p.long.learners_per_arm} learners, gap {GAP}): error "
        + ", ".join(
            f"{f3(long_curve[k])} after {k}"
            for k in (0, 30, 60, 100, len(long_curve) - 1)
            if k < len(long_curve)
        )
        + ".",
        "",
        "![Cumulative regret](figures/regret.png)",
        "",
        "## 4. Does the loop invent preferences?",
        "",
        f"A population with **no** true style preference (all three style traits 0.5), gap {GAP}. "
        f"Share of final style-trait estimates more than {metrics.FALSE_PREFERENCE} from 0.5:",
        "",
        "| arm | claimed-preference share | mean distance from 0.5 |",
        "|---|---|---|",
        *(f"| {LABEL[arm]} | {f3(share)} | {f3(dist)} |" for arm, (share, dist) in null.items()),
        "",
        "## 5. Behavioural traits (persistence, self-efficacy)",
        "",
        "| closed loop, gap world | error at the end |",
        "|---|---|",
        f"| EWMA off (new default) | {f3(closed_g['behaviour_mae'])} |",
        f"| EWMA on, rate 0.05 (v0 default) | {f3(behaviour_on['behaviour_mae'])} |",
        "",
        "The EWMA pulls each trait toward its raw proxy (share of 'kept going after a wrong "
        "answer', calibrated confidence). Nothing guarantees that a proxy's average equals the "
        "trait, so the estimate drifts away from the truth.",
        "",
        "## 6. Parameter sweep (closed loop, gap world, same learners for every setting)",
        "",
        "| ε | questionnaire variance | style-trait error | regret / expl. | non-greedy "
        "| learning gain |",
        "|---|---|---|---|---|---|",
        *(
            f"| {eps} | {var} | {f3(s['style_mae'])} ± {f3(s['style_mae_se'])} | "
            f"{f3(s['regret_per_step'])} | {s['non_greedy_share']:.1%} | {f3(s['learning_gain'])} |"
            for eps, var, s in sweep
        ),
        "",
        "ε is the forced-exploration floor; Thompson sampling explores on top of it. "
        "'Non-greedy' is the share of styles that differ from the posterior-mean best.",
        "",
        "## 7. Limitations",
        "",
        "- **Well-specified world.** Simulated learners respond exactly the way the bandit "
        "assumes, so recovery here is an upper bound.",
        "- **Assumed noise levels.** Clarity noise, dismissal rate, micro-check answer rate, "
        "questionnaire noise and the self-report gap are guesses. The pilot (R8) must measure "
        "them; the gap matters most.",
        "- **Assumed style effect size.** `explanation_fit_gain` sets how much a well-fitting "
        "style helps learning. Learning-gain differences scale with it, so they show the "
        "mechanism, not the size of the real effect.",
        "- **Trait scale.** Reported traits assume one trait unit moves y by κ. If real y responds "
        "more or less strongly, estimates are stretched or shrunk toward 0.5. Style *choice* is "
        "unaffected, but the pilot should estimate κ.",
        "- The fake explainer returns the concept card. Explanation content quality is not "
        "simulated.",
        "",
    ]
    (args.out / "simulation.md").write_text("\n".join(lines))
    print(f"wrote {args.out / 'simulation.md'} in {elapsed:.1f} min")


if __name__ == "__main__":
    main()
