# Model Specification (v0: starting point for Ronit)

This is the **initial** math. Ronit owns it and may change it. Every change
must be reflected here in the same PR as the code, with the reason.
Constants marked *(tune)* are first guesses that get re-checked with the
simulator (R6) and the pilot data.

---

## 1. Mastery: Bayesian Knowledge Tracing (BKT)

Each concept `c` has global parameters `p_init, p_learn (t), p_slip (s), p_guess (g)`.
Start with `p_init=0.2, t=0.15, s=0.1, g=0.2` *(tune)*. For MCQ with *k*
options, set `g ≈ 1/k`.

Observation update, with `L = P(mastered)`:

```
correct:   L' = L(1−s) / ( L(1−s) + (1−L)g )
incorrect: L' = L·s    / ( L·s    + (1−L)(1−g) )
transition: L_next = L' + (1−L')·t
predicted P(correct) = L(1−s) + (1−L)g        # used by drift and the bandit
```

**Prerequisite-informed prior.** For a concept the learner has never
attempted:
`p_init(c) = clip(base_init · (0.5 + mean_{p ∈ prereqs(c)} L_p), 0.05, 0.6)`.
A concept with no prerequisites uses `base_init`.

**Misconceptions.** A wrong MCQ answer whose option maps to misconception `m`
adds `m` to `misconception_ids`. `m` is removed after two consecutive correct
attempts on that concept.

## 2. Psychometric traits

Each of the five traits is stored as `{mean ∈ [0,1], variance, n_observations}`.

### 2.1 Prior from the questionnaire (R3)

- About 4 Likert items per trait, with reverse-scored items flipped.
- `mean = (avg − 1) / 4`.
- `variance = 0.04` (SD 0.2) *(tune)*, since short scales are noisy.

### 2.2 Style-identifiable traits: Bayesian linear bandit (core novelty)

The traits `abstraction_preference`, `load_tolerance` and `depth_preference`
are learned from **how the learner responds to different explanation styles**.

Style feature vector `x(s)` (with a leading 1 for the intercept):

| feature | value |
|---|---|
| intercept | 1 |
| `x_abs` | +1 if `example_first=False` (rule-first), −1 otherwise |
| `x_load` | −1 short, 0 medium, +1 long |
| `x_depth` | +1 `why`, −1 `how` |

Outcome `y` for one explanation, built from `ExplanationFeedbackSummary`
(code: `backend/app/learner_model/updates.py`):

```
y = [0.6·(followup_correct − p̂_correct) + 0.3·(clarity_rating − 3)/2] / (weights present)
    − 0.1 if dismissed_quickly
```

- `p̂_correct` is the BKT prediction for the micro-check, using mastery from
  *before* that attempt (read from the attempt's `state_updates` delta). This
  mastery adjustment keeps weak concepts from making every style look bad.
- If neither a follow-up answer nor a clarity rating exists, there is no
  bandit update. A quick dismissal alone is too weak a signal.

> *Changed in R5:* v0 renormalised over all three parts, including the
> dismissal term. A bare dismissal then became `y = −1`, a strong signal from
> a weak cue. The dismissal is now a fixed penalty on an otherwise
> informative outcome.

Model (θ measured in **trait units**, so a trait τ ∈ [0,1] corresponds to
`θ_k = κ(2τ_k − 1)`):

```
y = θ·x(s) − c·x_load² + ε,   ε ~ N(0, σ² = 0.25)  (tune)
κ = 0.3   (largest effect of one style feature on y)  (tune)
c = κ/2   (fixed curvature: `medium` wins while 0.25 < τ_load < 0.75)
```

The per-learner posterior is `θ ~ N(μ, Λ⁻¹)`. `Λ` (4×4), `b` (4) and the
observation count `n` are stored in `learner_traits.bandit`. Code:
`backend/app/learner_model/bandit.py`.

- **Prior from the questionnaire:** `μ0 = [0, κ(2q_abs−1), κ(2q_load−1), κ(2q_depth−1)]`.
  Variances: `[0.25, 4κ²·v_abs, 4κ²·v_load, 4κ²·v_depth]`, where `v = 0.04` is
  the questionnaire trait variance. `Λ0 = diag(1/variances)`.
- **Update:** `Λ ← Λ + x xᵀ/σ²`, `b ← b + x·(y + c·x_load²)/σ²`, `μ = Λ⁻¹ b`.
- **Reported trait:** `mean_k = (clip(μ_k/κ, −1, 1) + 1) / 2`,
  `variance_k = min(0.25, (Λ⁻¹)_kk / 4κ²)`. At the prior, these equal the
  questionnaire mean and variance exactly.

> *Changed in R3 (from v0):* v0 reported `(μ+1)/2` while the prior was
> `κ(2q−1)`, which squashed questionnaire scores toward 0.5 (q = 1 was
> reported as 0.65). v0's linear model also could never choose `medium`
> length. Both are fixed by the trait-unit scaling and the curvature term.

**Style choice in the `closed_loop` arm (R5).**

1. With probability `ε_min = 0.1`, pick one of the 12 (example_first ×
   length × depth) combinations at random. Set `style_source="exploration"`.
2. Otherwise, sample `θ̃ ~ N(μ, Λ⁻¹)` and pick the style that maximises
   `θ̃·x(s) − c·x_load²`. Set `style_source="thompson"`.
3. Affect constraints are applied *before* choosing, by shrinking the
   candidate set: `fatigue > 0.7` allows only `short`. This and rule 4 apply
   to both personalised arms (`static_personalized` and `closed_loop`).
4. `tone = "encouraging"` if `self_efficacy.mean < 0.4` or
   `frustration > 0.6`. `include_diagram = concept card has a diagram and
   x_abs = −1`.

> *Checked in R6 (`research/reports/simulation.md` §6):* ε ∈ {0, 0.05, 0.1} ×
> questionnaire variance ∈ {0.04, 0.09}. **Kept ε = 0.1 and variance = 0.04.**
> - ε = 0.1 gave the best trait recovery (error 0.101 vs 0.124 at ε = 0, about
>   2 SE apart) for about 10% more regret (0.149 vs 0.134).
> - The variance difference was within 1 SE.
> - The bigger lever is Thompson sampling itself: 53–61% of choices differ from
>   the posterior-mean best style. That makes the closed loop pay more regret
>   than the static arm for roughly the first 100 explanations (§3 of the
>   report). Trading recovery for regret (e.g. greedy on the posterior mean,
>   plus ε) is a design decision for Ronit, not a constant to tune.

**`static_personalized` arm.** Pick the style that maximises the **prior
mean** (no sampling, no updates from feedback; `style_source="trait_mapped"`).
This is the same rule the bandit uses, so the arms differ only in learning.
It works out to:
- `example_first` if `abstraction < 0.5` (ties go to example-first)
- `length`: short if `load < 0.25`, long if `load > 0.75`, medium otherwise
- `depth = why` if `depth > 0.5`

**`generic` arm.** Always `example_first=True, length=medium, depth=how,
tone=neutral, include_diagram=card has diagram`, with
`style_source="generic"`.

### 2.3 Behavioural traits: EWMA

Only in the `closed_loop` arm; the other arms keep their questionnaire
values.

> **Off by default since R6** (`LearnerModel(behaviour_alpha=0.0)`). The R6
> simulation (`research/reports/simulation.md` §5) shows that the EWMA makes
> persistence and self-efficacy estimates *worse* than the questionnaire
> alone. It pulls each trait toward its raw proxy, but nothing guarantees
> `E[proxy | trait] = trait`; for example, most learners keep going after a
> wrong answer whatever their persistence. To re-enable it, first calibrate
> each proxy on pilot data (R8): regress the per-learner proxy rate on the
> questionnaire score (`proxy ≈ a + b·trait`), then run the EWMA on the
> implied trait `(proxy − a)/b` at rate α = 0.05.

The proxies, kept for when calibration exists:

- `persistence`: after a wrong answer, the next attempt gives proxy 1 if it
  comes within the same session (gap ≤ 30 min) and 0 if the session ended
  there. Sessions are detected by a gap, so "quit within 60 s" (v0) is
  approximated by "the next attempt is in a new session".
- `self_efficacy`: per attempt with a confidence rating,
  `proxy = clip(c − |c − correct|, 0, 1)`, where `c = (confidence − 1)/4`.
  Confident and right gives 1; confident and wrong gives 0.
- Update with `α = 0.05` *(tune)*:
  `mean ← (1−α)·mean + α·proxy`, `variance ← max(0.005, variance·(1−α))`.

## 3. Explanation feedback → concept graph

- A follow-up micro-check is an ordinary attempt, so it goes through BKT
  (§1).
- `clarity_rating ≤ 2` **and** `followup_correct = False` →
  `misconception_suspicion += 0.25` (capped at 1).
- `followup_correct = True` → `misconception_suspicion *= 0.5`.
- The planner remediates when `misconception_suspicion ≥ 0.5`, with reason
  `MISCONCEPTION_SUSPECTED`.

## 4. Affective state (session-level, rolling)

| Signal | Update |
|---|---|
| `engagement` | EWMA(α=0.2) of `1 − dismissed_quickly`, per explanation |
| `frustration` | EWMA(α=0.3) of "wrong and (latency < 3 s or 2+ consecutive wrong)" |
| `fatigue` | `min(1, minutes_in_session / 40)`, + 0.2 if accuracy over the last 5 is 0.3 or more below the session mean |

A new session starts when the gap since the previous attempt is more than
30 minutes. Affect updates in every arm.

## 5. Planner rules (R4), in priority order

Code: `backend/app/planner/service.py`. Only concepts with approved practice
items are candidates. Every decision carries `ReasonEvidence`.

1. **Diagnostic:** fewer than 8 attempts in total → an unattempted concept at
   a target depth that sweeps the graph (fractions 0, .25, .5, .75, .1, .35,
   .6, .85 of the maximum depth). Ties are broken by a seeded RNG. Reason
   `DIAGNOSTIC`.
2. **Misconception:** any concept with `misconception_ids` or
   `misconception_suspicion ≥ 0.5` → remediate the weakest such concept.
   Reason `MISCONCEPTION_DETECTED` (one per flag, detail = description) or
   `MISCONCEPTION_SUSPECTED`.
3. **Prerequisite gap:** the last 2 attempts on concept c were wrong
   (`streak ≤ −2`) and some prerequisite p has `L_p < 0.6` → remediate the
   weakest p. The most recently practised struggling concept is checked first.
   Reason `PREREQ_GAP` (detail names c).
4. **Review turn:** when a review is due, every 6th step
   (`total_attempts % 6 == 5`) is a review (rule 6).
5. **Frontier:** concepts whose prerequisites all have `L ≥ 0.85` and whose
   own `L < 0.95`.
   - If any of them is in progress (attempted), continue the weakest one
     (`practice_item`).
   - Otherwise advance to the first one in topological order (`advance`).
   - Reason `READY_FOR_NEXT`.
6. **Review:** a mastered concept (`L ≥ 0.95`) not practised for 48 h → the
   stalest one. Reason `REVIEW_DUE`.
7. **Fallback:** the weakest concept with items, as a review.

**Item choice:** among the concept's practice items not in the learner's last
10 attempts (or all of them, if every item is recent), minimise
`|p̂_correct − 0.7| + 0.05·|difficulty − (1 + round(4L))|`. Ties go to the
item id.

> *Changed in R4 (from v0):*
> - Frontier: v0 picked the lowest-L frontier concept. Unattempted concepts
>   have low priors, so the learner was always pulled to something new
>   before finishing the current concept.
> - Review: v0 only reviewed once the frontier was empty, which with ~60
>   concepts almost never happens.

## 6. Research only (R8): resonance and drift

- **Resonance** (fixed version of the deck's formula):
  `R = P^0.25 · C^0.25 · B^0.25 · T^0.25`
  - `P = sigmoid(μ·x(s_last))` (style fit)
  - `C = L` (mastery)
  - `B = 1 − normalised variance of recent correctness`
  - `T = clip(expected_latency / latency, 0, 1)`
  - Compare against a logistic-regression baseline on the same features.
- **Drift:** residuals `r_t = o_t − p̂_t`. CUSUM `S_t = max(0, S_{t−1} − r_t −
  k)` with `k = 0.1`; alert when `S_t > h = 1.0` *(tune)*.
- **Backtest metric** (as implemented in `research/backtest/early_warning.py`, R8):
  - A struggle run is two wrong answers in a row on one concept, the equivalent of
    Phase-1's "score < 0.7".
  - An alarm warns early if it switched on within the 5 answers up to and including the
    run's *first* wrong answer, i.e. before performance visibly dropped.
  - Report recall, precision, median lead and alarm rate, against a naive
    "last answer wrong" baseline.
  - In the resonance score, P is approximated by the latest clarity rating on the concept
    (0.5 if none), because the per-step bandit fit is not logged.
