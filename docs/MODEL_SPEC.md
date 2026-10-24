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

Outcome `y` for one explanation, built from `ExplanationFeedbackSummary`.
Weights are renormalised over the components that are present; if none are
present, no update happens.

```
y = 0.6·(followup_correct − p̂_correct)      # mastery-adjusted, so weak concepts don't punish every style
  + 0.3·(clarity_rating − 3)/2
  + 0.1·(−1 if dismissed_quickly else 0)
```

Model: `y = θ·x(s) + ε`, with `ε ~ N(0, σ²=0.25)` *(tune)*. The per-learner
posterior is `θ ~ N(μ, Λ⁻¹)`. `Λ` (4×4) and `b` (4) are stored in
`learner_traits.bandit`.

- Prior: `μ0 = [0, κ(2q_abs−1), κ(2q_load−1), κ(2q_depth−1)]`, with `κ = 0.3`
  and `q` = questionnaire means. `Λ0 = I / 0.25`.
- Update: `Λ ← Λ + x xᵀ/σ²`, `b ← b + x·y/σ²`, `μ = Λ⁻¹ b`.
- Reported trait: `mean_k = (clip(μ_k, −1, 1) + 1) / 2`.
  `variance_k = (Λ⁻¹)_kk / 4`.

**Style choice in the `closed_loop` arm (R5).**

1. With probability `ε_min = 0.1`, pick one of the 12 (example_first ×
   length × depth) combinations at random. Set `style_source="exploration"`.
2. Otherwise, sample `θ̃ ~ N(μ, Λ⁻¹)` and pick the style that maximises
   `θ̃·x(s)`. Set `style_source="thompson"`.
3. Affect constraints are applied *before* choosing, by shrinking the
   candidate set: `fatigue > 0.7` allows only `short`.
4. `tone = "encouraging"` if `self_efficacy.mean < 0.4` or
   `frustration > 0.6`. `include_diagram = concept card has a diagram and
   x_abs = −1`.

**`static_personalized` arm.** Map the questionnaire means directly
(`style_source="trait_mapped"`), with no updates from feedback:
- `example_first = abstraction < 0.5`
- `length`: short if `load < 0.35`, long if `load > 0.7`, medium otherwise
- `depth = why` if `depth ≥ 0.5`

**`generic` arm.** Always `example_first=True, length=medium, depth=how,
tone=neutral, include_diagram=card has diagram`, with
`style_source="generic"`.

### 2.3 Behavioural traits: EWMA

- `persistence`: proxy ∈ {0,1} per wrong answer, equal to 1 if the learner
  retries or continues instead of quitting the session within 60 s.
- `self_efficacy`: proxy = mean of normalised confidence ratings, minus the
  miscalibration `|confidence − correctness|`.
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
| `engagement` | EWMA(α=0.2) of `1 − dismissed_quickly`, plus micro-check completion |
| `frustration` | EWMA(α=0.3) of "wrong and (latency < 3 s or 2+ consecutive wrong)" |
| `fatigue` | `min(1, minutes_in_session / 40)`, + 0.2 if accuracy over the last 5 is 0.3 or more below the session mean |

## 5. Planner rules (R4), in priority order

1. **Diagnostic:** fewer than 8 attempts in total → items from root and
   mid-depth concepts. Reason `DIAGNOSTIC`.
2. **Misconception:** any concept with `misconception_ids` or
   `misconception_suspicion ≥ 0.5` → remediate it. Reason
   `MISCONCEPTION_DETECTED` or `MISCONCEPTION_SUSPECTED`.
3. **Prerequisite gap:** the last 2 attempts on concept c were wrong and
   some prerequisite p has `L_p < 0.6` → remediate the weakest p. Reason
   `PREREQ_GAP`.
4. **Frontier:** among concepts whose prerequisites all have `L ≥ 0.85` and
   whose own `L < 0.95`, pick the lowest `L`. Reason `READY_FOR_NEXT`.
5. **Review:** a mastered concept not practised in the last 2 sessions →
   `REVIEW_DUE`.

Item difficulty: target an item with `p̂_correct ≈ 0.7`.

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
- **Backtest metric:** for each real failure (score < 0.7), how many tasks
  *earlier* the alert fired, plus precision and recall of the alerts.
