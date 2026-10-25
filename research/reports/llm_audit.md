# Explanation audit (inter-rater reliability)

**Status: not conducted yet.** No explanations have been rated by people.

An earlier version of this file reported a Cohen's kappa of 0.906 and ratings attributed to Mit
and Ronit. Those ratings were hard-coded in `app/explainer/audit.py`, not given by anyone, so the
figures were withdrawn. They must not be cited.

## How to run the audit

From `backend/`:

1. `python -m app.explainer.audit sample --n 100 --out audit.csv` draws 100 explanations across
   concepts and style buckets and records an automatic grounding check.
2. Mit and Ronit each fill in their own column (`rater_mit`, `rater_ronit`) **independently**,
   with `correct`, `minor_issue` or `wrong` (scale in `docs/EVALUATION_PLAN.md`).
3. `python -m app.explainer.audit score audit.csv` checks that every row has both ratings, computes
   Cohen's kappa, and overwrites this file with the results.

Targets (pre-registered): kappa >= 0.85, explanations rated `wrong` <= 2%.
