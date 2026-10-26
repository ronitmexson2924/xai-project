# Explainability (XAI) Design

The project's claim is that the *adaptation itself* is explainable to the learner, not just
the content. This doc defines what the app must explain, how the explanations stay **faithful**
(true to what the model actually did), and who builds what.

## 1. Status

| Part | Status | Where |
|---|---|---|
| Contract (`contracts/xai.py`, `ExplainabilityService`, fakes, `why_*` events) | ✅ Merged | `backend/app/contracts/` |
| E1 + E2: decision rationale and verified counterfactuals (R9) | ✅ Built and tested | `app/planner/rationale.py`, `app/planner/policy.py` |
| E3: style rationale with `p_best` (R10) | ✅ Built and tested | `app/planner/style.py` (`explain_style`) |
| E4 + E5: beliefs and change notices (R10) | ✅ Built and tested | `app/learner_model/explain.py` |
| One service for the API (R10) | ✅ `Explainability(learner_model)` | `app/planner/xai.py` |
| Evaluation measures (R11) | ✅ In the pre-registration (X1, X2) and `research/analyze.py` | `research/` |
| API endpoints (M9) | ✅ `GET /recommendations/{id}/why`, `GET /learners/me/explain`, `change` on answers and close | `backend/app/api/` |
| UI panels (M10) | ✅ "Why this?" panel with 1-tap rating, belief panels on the dashboard, change notices | `frontend/src/components/` |
| Performance model + post-hoc XAI (§7) | ✅ Trained MLP; SHAP, LIME, LRP, DiCE per prediction; model card | `backend/app/ml/`, `GET /recommendations/{id}/model`, `/model` page |

**See it now:** `cd backend && python -m app.planner.xai_demo` prints every explanation for the
three demo learners (rolled back; the database is unchanged).

How the rationale is stored: `Planner.next_step` builds the `Rationale` from its decision trace
and saves it in `recommendations.rationale`. `Planner.choose_style` saves the `StyleRationale` on
the same recommendation. `Explainability.why(recommendation_id)` returns both exactly as
stored, never recomputed.

## 2. The five things the app explains

| # | Question the learner can ask | Answer is built from | Owner |
|---|---|---|---|
| E1 | **Why this question / topic now?** | The planner rule that fired, with the actual numbers and thresholds, and the alternative it passed over | Ronit (rationale), Mit (UI) |
| E2 | **What would change it?** (counterfactual) | Re-running BKT forward: "about 2 more correct answers on X and you move on to Y", verified by re-running the planner | Ronit |
| E3 | **Why is this explanation written this way?** | Style choice and its source. "Example first: it has worked better for you (we're fairly sure, 9 explanations)", or "We're trying a different style to learn what suits you" | Ronit (rationale), Mit (UI) |
| E4 | **Why do you think that about me?** (open learner model) | The `state_updates` events that moved a belief most, plus uncertainty | Ronit (attribution), Mit (dashboard) |
| E5 | **What did my feedback change?** (closing the loop) | The `StateDelta` from `apply_explanation_feedback`: "You rated the last explanation unclear, so we'll keep explanations shorter for now" | Ronit (text), Mit (toast/notice) |

Concept-level *teaching* explanations (the concept card rephrased for the learner, Module B)
are Mit's explainer and are separate from these. When they cite a reason, they must use E1's
text, not invent one.

## 3. Faithfulness rules (what makes this XAI rather than decoration)

1. **Generated from the decision, not after it.** The planner returns a trace of the rule
   that fired, the evidence values, the thresholds and the runner-up. E1/E2 are built only
   from that trace. No post-hoc guessing.
2. **Counterfactuals are verified.** For every E2 "what would change it", a test applies the
   counterfactual to the learner state, re-runs the planner, and checks that the decision
   actually changes.
3. **Uncertainty is shown, never hidden.** Traits with variance above a threshold, or fewer
   than 5 observations, are phrased as tentative. Exploration choices say they are
   experiments.
4. **The LLM may rephrase but not change facts.** Mit's explainer keeps every number and
   concept name from the rationale; a validator rejects outputs that drop or alter them.
5. **No psychological labels.** Never "you are a visual learner" or "low persistence". Say
   what was observed and what the system will do: "explanations with an example first have
   worked better for you".

## 4. Contract additions (one `contract` PR, both approve)

```python
# backend/app/contracts/xai.py
class Counterfactual(BaseModel):
    condition: str            # "answer 2 more questions on Recursion: base case correctly"
    concept_id: str
    target_value: float       # threshold that flips the decision, e.g. 0.60
    steps_needed: int | None  # e.g. 2 correct answers (BKT forward simulation)
    outcome: str              # "you move on to Recursion: recursive case"

class Rationale(BaseModel):   # E1 + E2 for one Recommendation
    recommendation_id: UUID
    rule: ReasonCode
    summary: str              # one learner-facing sentence, plain language
    evidence: list[ReasonEvidence]
    threshold: float | None
    alternative: str | None   # what it would otherwise have recommended
    counterfactuals: list[Counterfactual]

class StyleRationale(BaseModel):  # E3
    source: StyleSource
    summary: str
    p_best: float | None      # posterior probability this style is best for the learner
    confidence: Literal["tentative", "moderate", "confident"]

class BeliefExplanation(BaseModel):  # E4
    subject: str              # concept id or trait name
    value: float
    confidence: Literal["tentative", "moderate", "confident"]
    top_evidence: list[str]   # the events that moved it most, newest first
```

## 5. How we will evaluate the explanations

Add to `research/preregistration.md` before sign-off:

- **Faithfulness:** automated. Every counterfactual flips the planner in tests; target 100%.
- **Comprehensibility:** 1-tap "Did this make sense?" on the "Why this?" panel (about 1 in 5).
  Report the distribution per arm.
- **Usefulness:** three post-test survey items, e.g. "I understood why the app chose my next
  question". Report means and CIs.
- **Behaviour:** do learners who open "Why this?" accept recommendations more, or skip them
  less? Exploratory.

## 6. Example (demo learner Ben, from `app.graph.demo_seed`)

> **Why this question?** On a recursion question you picked *"It never returns"*, which matches
> a common misunderstanding: *believing recursion stops on its own without a base case*.
> We're fixing that before moving on.
> **What would change it?** Two correct answers in a row on *Recursion: base case* clear
> this, and then you go on to *Recursion: recursive case*.
> **Why does the explanation look like this?** Your questionnaire suggests examples help you
> (tentative: no explanation feedback yet).

## 7. Post-hoc explanations of a trained model (SHAP, LIME, LRP, DiCE)

E1–E5 explain transparent models (BKT, the bandit, the rule planner) *from their own
decision traces*. To also cover the standard post-hoc methods, the app has a trained neural
network: the performance model (`docs/MODEL_SPEC.md` §7), which predicts P(correct) for each
question. After each answer the learner sees what it predicted, and why, four ways. All of it
runs in Python on the server; no external AI service is involved.

| Method | Question it answers | Implementation | Checked by tests |
|---|---|---|---|
| SHAP (Lundberg & Lee, 2017) | How much did each factor move the prediction away from the average learner's? | `shap` library, permutation algorithm, 200-row reference sample | Additivity: base + contributions = prediction; a factor the model ignores gets 0 |
| LIME (Ribeiro et al., 2016) | What simple linear story fits the network near this learner? | `lime` library, 2,000 perturbed samples; the surrogate's R² is shown | Recovers a nearly linear model and its top factor |
| LRP (Bach et al., 2015) | How is the network's output passed back through its layers onto the inputs? | Epsilon rule on the network's weights, in `app/ml/explain.py` | Conservation: inputs + bias share = logit; weight × input on a linear model |
| DiCE (Mothilal et al., 2020) | What realistic changes would flip the prediction? | DiCE's loss (hinge validity + MAD-weighted proximity − DPP diversity) minimised by gradient descent, then DiCE's post-hoc sparsity step, in `app/ml/explain.py`. Only actionable factors move, within plausible ranges, and answered-question counts never decrease. | Every counterfactual flips the prediction, changes only actionable factors and stays in range |

`dice-ml` was not used because it would add about 430 MB of unused GPU and boosting libraries.
LRP has no scikit-learn implementation.

**Faithfulness and honesty measures,** reported per prediction and in the model card
(`research/reports/performance_model.md`):
- agreement between methods (Spearman ρ between SHAP, LIME and LRP);
- LIME's local R²;
- counterfactual validity, sparsity and how often one is found;
- a deletion test: removing SHAP's top 3 factors must move the prediction more than removing
  3 random ones.

When LIME fits poorly or the methods disagree, the panel says so.

**Scope:** these explain the performance model's prediction, not the planner's choice (that is
E1–E2), and not causes in the learner.

