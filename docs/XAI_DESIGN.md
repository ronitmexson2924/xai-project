# Explainability (XAI) Design

The project's claim is that the *adaptation itself* is explainable to the learner, not just
the content. This doc defines what the app must explain, how the explanations stay **faithful**
(true to what the model actually did), and who builds what.

## 1. Status

| Part | Status | Where |
|---|---|---|
| Contract (`contracts/xai.py`, `ExplainabilityService`, fakes, `why_*` events) | ✅ Built; **needs both approvals** (branch `contract/xai`) | `backend/app/contracts/` |
| E1 + E2: decision rationale and verified counterfactuals (R9) | ✅ Built and tested | `app/planner/rationale.py`, `app/planner/policy.py` |
| E3: style rationale with `p_best` (R10) | ✅ Built and tested | `app/planner/style.py` (`explain_style`) |
| E4 + E5: beliefs and change notices (R10) | ✅ Built and tested | `app/learner_model/explain.py` |
| One service for the API (R10) | ✅ `Explainability(learner_model)` | `app/planner/xai.py` |
| Evaluation measures (R11) | ✅ In the pre-registration (X1, X2) and `research/analyze.py` | `research/` |
| API endpoints (M9) and UI panels (M10) | ⏳ Mit | `backend/app/api/`, `frontend/` |

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
