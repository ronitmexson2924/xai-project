# Project Brief

## What we are building

An adaptive learning web app for **Data Structures & Algorithms (DSA)**. It
keeps a **unified learner state** for each student:

- a **concept-mastery graph**: about 60 DSA concepts, prerequisite edges, a
  mastery probability per concept, and misconception flags;
- a **psychometric trait vector**: five traits, each stored as mean +
  uncertainty;
- a short-term **affective state**: engagement, frustration, fatigue.

For every recommendation (next item, remediation, moving on), the app shows a
**concept-level explanation** whose presentation (example-first or rule-first,
length, why/how depth, tone) is chosen from the learner's traits. The learner's
**interaction with that explanation** (visible dwell time, expand, replay,
1-tap clarity rating, follow-up micro-check) is logged and **fed back** into
both the trait vector and the mastery graph. That closes the loop.

## The one claim we must prove

> Treating explanation interaction as a feedback signal, with explanation
> style chosen by a trait model and varied deliberately, gives (a) better
> prediction of the learner's next answer and (b) better follow-up correctness
> than generic explanations.

Everything in the scope below exists to build and measure this claim. See
`EVALUATION_PLAN.md`.

## Modules (from the patent document, renamed to code packages)

| Module | Meaning | Code package | Owner |
|---|---|---|---|
| A: Unified Learner State | mastery graph + traits + affect | `backend/app/learner_model`, `backend/app/graph`, `backend/app/psychometrics` | Ronit |
| B: Concept Explanation Generator | trait-conditioned, grounded explanations | `backend/app/explainer` | Mit |
| C: Explanation-Feedback Analyzer | capture + summarise interaction (Mit); turn it into state updates (Ronit) | `backend/app/telemetry` (Mit) → `learner_model.apply_explanation_feedback` (Ronit) | Both, split at `ExplanationFeedbackSummary` |
| D: Adaptive Path Re-Planner | next step, reasons, style selection | `backend/app/planner` | Ronit |
| API + UI | endpoints, Next.js app, dashboards | `backend/app/api`, `frontend/` | Mit |
| Research | simulator, evaluation, resonance/drift backtest | `research/` | Ronit |

## Design decisions (binding unless changed by a contract PR)

- **D1 Domain:** DSA only, 50–80 concepts (target 60), clustered as basics,
  arrays & strings, linked structures, recursion, sorting & searching, trees,
  graphs, DP.
- **D2 Stack:**
  - Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16.
  - Frontend: Next.js (App Router, TypeScript, Tailwind).
  - LLM: Gemini through the `google-genai` SDK, with model names set in `.env`.
- **D3 Mastery model:** Bayesian Knowledge Tracing per concept, with the
  prior raised or lowered by prerequisite mastery. Parameters are fitted
  globally.
- **D4 Traits:** five traits, each a Gaussian (mean in [0,1], variance):
  `abstraction_preference`, `load_tolerance`, `depth_preference`,
  `persistence`, `self_efficacy`. **No learning styles** (see
  `CRITICAL_REVIEW.md` §2.3).
- **D5 Style:** `StyleParams` has a small discrete space:
  - `example_first` × `length` × `depth`: 12 LLM-generated variants per concept;
  - `tone` and `include_diagram`: applied by a template wrapper.
- **D6 Explanations are grounded and precomputed.** The LLM rephrases a
  curated **concept card** and does not invent facts. Variants are generated
  offline, validated and spot-reviewed, then served from the database. Live
  LLM calls are a fallback with a timeout, and a template fallback always
  exists.
- **D7 Causal assignment:**
  - follow-up correctness updates mastery (BKT);
  - style contrast updates the three style-identifiable traits (Bayesian
    linear bandit);
  - behavioural proxies update persistence and self-efficacy;
  - low clarity together with a wrong follow-up raises misconception
    suspicion.
- **D8 Exploration:** in the `closed_loop` arm, style is chosen by Thompson
  sampling with a minimum exploration rate, so the loop can't lock itself in.
- **D9 Experiment arms:**
  - `generic`: same style for everyone;
  - `static_personalized`: style from questionnaire traits, no feedback
    updates;
  - `closed_loop`: the full system.
  Users are assigned to arms at signup with balanced randomisation.
- **D10 Phase-2 ideas are research only.** Resonance and drift are
  implemented in `research/` and backtested. They do not drive live decisions
  in this project unless the backtest shows real lead time.
- **D11 Privacy:** consent screen, pseudonymous IDs in exports, a
  delete-my-data endpoint, and no third-party analytics.

## Explicit non-goals

- More than one subject domain.
- Training RL policies, or per-learner edge-weight evolution. Global edge
  weights may be re-estimated offline.
- Camera, voice or other emotion sensing.
- Native mobile apps. A responsive web app is enough.
- Production multi-tenant scale. Target: about 100 concurrent users.

## Glossary

- **Concept card:** curated, reviewed facts for one concept: definition, key
  idea, worked example, common pitfall, and an optional diagram. It is the
  only factual source the explainer may use.
- **Micro-check:** one quick question asked right after an explanation to
  test whether it worked.
- **Reason evidence:** a machine-readable reason for a recommendation, e.g.
  `PREREQ_GAP(recursion-base-case, p=0.41)`. Explanations must cite it.
- **Style bucket:** one combination of `StyleParams`, used as a cache key.
