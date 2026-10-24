# Evaluation Plan

Without evaluation, this project is a demo. With it, it becomes a result.
There are three layers: **offline simulation** (R6), **system quality** (Mit),
and the **pilot with real students** (both).

## Hypotheses

| ID | Hypothesis | Primary metric | Data | Expected power |
|---|---|---|---|---|
| **H1** | Adding explanation-interaction features improves prediction of the next answer | AUC and log-loss of next-attempt correctness: BKT alone vs BKT + feedback features (5-fold CV, split by learner) | Pilot logs (all arms) | Good: thousands of attempts |
| **H2** | Trait-conditioned style raises micro-check correctness compared with the generic style | Mixed-effects logistic regression, `followup_correct ~ arm + concept + (1 \| learner)` | Pilot, with micro-randomisation inside `closed_loop` | Moderate: hundreds of explanations per arm |
| **H3** | The closed loop recovers true preferences and does not lock in | Trait recovery error (MAE between true and estimated), share of styles explored, regret | Simulator (R6) | Full control |
| **H4** | The full system improves learning gain | Normalised gain `(post − pre)/(1 − pre)` on a 15-item pre/post test | Pilot | **Low.** Report the effect size with a 95% CI. Do not claim significance you don't have. |
| **H5** *(research)* | Drift and resonance alerts come before failure | Lead time in tasks, precision and recall of alerts | Pilot logs (R8) | Exploratory |

## System quality (Mit, M7)

- **Explanation correctness audit:** 100 random explanations, each rated by
  both Ronit and Mit on a 3-level scale (correct / minor issue / wrong).
  Report Cohen's κ for agreement. Target: wrong < 2%.
- **Grounding check:** share of explanations that mention only concepts from
  the request. Target 100%, validated automatically.
- **Latency:** p50 and p95 per endpoint (budgets in `ARCHITECTURE.md`).
  **Fallback rate**, split into precomputed / llm / template.
- **Cost:** LLM tokens per learner-session.

## Pilot protocol (weeks 9–10)

1. **Ethics:** consent form approved by your guide or the institution
   (started in week 1, task S4).
2. **Recruitment:** 30–60 students who are taking or have taken DSA.
3. **Assignment:** balanced randomisation into `generic`,
   `static_personalized` and `closed_loop`. If N < 45, use two arms:
   `generic` and `closed_loop`.
4. **Day 1:** consent → questionnaire → **pre-test** (15 items, not reused
   in sessions) → first session.
5. **Days 2–12:** at least 4 sessions of 15 minutes.
6. **Last day:** **post-test** (a parallel form of the pre-test) + a SUS
   usability questionnaire + 3 open questions.
7. **Freeze:** no deploys to `main` during the pilot except critical fixes.

## Reporting rules

- Pre-register H1–H4 and the analysis code (commit them to
  `research/preregistration.md`) **before** pilot data comes in.
- Report every hypothesis, including null results.
- Report psychometric reliability (Cronbach's α per trait).
- Separate simulated results from real ones. Never mix them in one table.
