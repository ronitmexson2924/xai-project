# Pre-registration (task S2) — DRAFT, not yet signed off

> Drafted by Ronit's agent in R8. **Ronit and Mit (and the guide) must review, settle the open
> decisions in §7, and sign off in §8 before any pilot data is collected.** After sign-off,
> changes are allowed only as dated, explained amendments at the bottom.

## 1. Design

- Three arms, assigned at signup with balanced randomisation:
  - `generic`: one fixed explanation style for everyone;
  - `static_personalized`: style from the questionnaire, never updated;
  - `closed_loop`: Thompson sampling, updated from explanation feedback.
- If fewer than 45 learners are recruited, run two arms only (`generic`, `closed_loop`).
- The procedure is in `docs/EVALUATION_PLAN.md` ("Pilot protocol"). The model code version is
  frozen at the `main` tag used for the pilot (v0.9).
- Everything below runs with one command:
  `ANALYSIS_SALT=… PYTHONPATH=../research python ../research/analyze.py --from-db`.
  It writes `research/reports/results.md`.

## 2. Data definitions (as implemented in `research/analysis/export.py`)

- **Learner:** non-deleted user with an experiment arm. IDs are pseudonymised with a salted
  SHA-256 hash, and emails are never exported.
- **Practice answer:** an attempt that is not a micro-check and not a pre/post-test item.
- **p̂:** the live model's predicted P(correct) for the attempt, using mastery from just
  before the attempt (from `state_updates`), with the item's guess rate.
- **Explanation feedback:** the `explanation_feedback` summary (`ExplanationFeedbackSummary`).
- **Pre/post test:** attempts on items whose ID starts with `pretest-` / `posttest-`. They
  are recorded with `record_test_attempt` and never update the learner model.

## 3. Hypotheses and analyses

| ID | Question | Analysis (code) | Supported if |
|---|---|---|---|
| **H1** | Do explanation-interaction features improve prediction of the next practice answer? | Practice answers preceded by an explanation on the same concept. Logistic regression of correctness on logit(p̂), with and without the latest explanation's features (clarity, missing-clarity flag, log visible dwell, expanded, replays, quick dismissal, follow-up result). 5-fold CV split by learner; pooled out-of-fold AUC and log-loss; 95% learner-bootstrap CI (1,000 resamples) for the gains. (`hypotheses.h1`) | Both CIs (AUC gain, log-loss reduction) exclude 0. |
| **H2** | Does the arm change micro-check accuracy? | GEE logistic regression of micro-check correctness on arm (reference `generic`) + concept cluster, exchangeable working correlation within learner, robust SEs. (`hypotheses.h2`) | The `closed_loop` vs `generic` odds-ratio CI excludes 1. |
| **H3** | Does the loop recover preferences, without inventing them? | Simulation only (`research/reports/simulation.md`, R6). Not tested on pilot data, because true traits are unknown. | Reported as is. |
| **H4** | Does the full system improve learning gain? | Normalised gain `(post − pre)/(1 − pre)`, learners with pre < 1. Per-arm mean with bootstrap CI; difference vs `generic` with bootstrap CI and Cohen's d. (`hypotheses.h4`) | **Underpowered by design:** report effect sizes and CIs only, with no significance claim. |
| **H5** *(exploratory)* | Do drift or resonance alarms warn before struggle? | Struggle run = 2 wrong answers in a row on one concept. Early warning = an alarm onset within the 5 answers up to and including the run's first wrong answer. Recall, precision, median lead and alarm rate, against a naive "last answer wrong" baseline. (`backtest/early_warning.py`) | A detector beats the baseline on both lead and precision. Only then may it drive live decisions (D10). |
| Reliability | Are the questionnaire scales internally consistent? | Cronbach's α per trait. (`hypotheses.reliability`) | Reported; α < 0.6 flags the trait as unreliable. |
| **X1** *(XAI, descriptive)* | Are the adaptation's explanations faithful, used and understood? | (a) **Faithfulness**, automated before the pilot: every counterfactual in a rationale is carried out through the real learner model and must give the promised recommendation (`tests/test_rationale.py`). Coverage from the logs: share of recommendations with a rationale and with ≥ 1 counterfactual. (b) **Use**: "Why this?" opens per explanation shown. (c) **Comprehensibility**: share of 1-tap ratings that say helpful, with a learner-bootstrap CI. All per arm. (`hypotheses.xai`) | Descriptive. (a) must be 100% in CI; rationale coverage must be 100% of recommendations. |
| **X2** *(XAI, survey)* | Do learners feel they understand and can trust the adaptation? | Three 5-point items in the post-test survey: "I understood why the app chose my next question", "The explanations of my progress matched how I felt I was doing", "Knowing why helped me decide what to practise". Mean per arm with 95% CI. | Descriptive; reported with X1. |

**Deviation from `EVALUATION_PLAN.md`:** H2 there names a mixed-effects logistic regression. GEE
with learner clustering estimates the same population-level arm effect with robust standard
errors, and it is more stable at pilot sample sizes. The mixed model may be reported as a
sensitivity analysis.

## 4. Exclusions (decided now, not after seeing data)

- Learners who withdraw consent or ask for deletion are removed entirely.
- Learners with fewer than 5 practice answers are excluded from H1, H2 and H4, and the
  count is reported.
- No other exclusions: no outlier trimming, and no dropping of fast answers.

## 5. What the simulator says to expect (R6 and the R8 validation run)

These are numbers from simulated learners. They are expectations, not results.

- **H1:** a null result is likely. In the validation run (`results_simulated.md`, 90 learners)
  the AUC gain was 0.000 (CI −0.003 to +0.003), **even though the loop works in that world**.
  Feedback mostly says which *style* suits a learner, and BKT has already absorbed the
  follow-up answer. See open decision A.
- **H2:** detectable. In simulation, closed loop vs generic gave OR ≈ 1.4 with about 30
  learners per arm.
- **H4:** noisy. Simulated differences changed sign between runs with different seeds (R6 vs
  the R8 validation run).
- **Self-report gap:** the loop only adds value when self-report is wrong (R6). The pilot
  should report the gap between questionnaire traits and the closed-loop traits after the
  pilot.

## 6. Multiple comparisons

H1 and H2 are the confirmatory tests, each at α = 0.05. H4 and H5 are descriptive and
exploratory. All results are reported, including nulls.

## 7. Open decisions (settle before sign-off)

- **A. Primary claim.** Should H1 stay the primary confirmatory test? The simulation suggests
  it can be null for a system that works. Alternatives:
  - make H2 primary;
  - add **H1b**: "the closed loop's style-trait estimates after the pilot predict micro-check
    success on held-out explanations better than the questionnaire traits do".
- **B. Explore/exploit.** Keep full Thompson sampling, which is best for identifying traits,
  or exploit more, which is better for short-term learning (R6 finding 3;
  `docs/MODEL_SPEC.md` §2.2 "Checked in R6")?
- **D. Explanations in the `generic` arm.** Decision rationales (why this question, what would
  change it) are shown in every arm, because the planner is the same for all arms. Only the
  *style* rationale differs between arms. Confirm this, or hide "Why this?" in `generic` to
  test the explanations themselves (that adds a factor and lowers power).
- **C. Pilot length.** About 40 explanations per learner is enough for H2 but leaves trait
  recovery partial (R6). Can sessions be extended?

## 8. Sign-off

| Name | Role | Date | Signature |
|---|---|---|---|
| Ronit | learner model, analysis | | |
| Mit | system, data collection | | |
| Guide | supervision | | |

## Amendments

_(none yet)_
