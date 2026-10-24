# Team Plan: Who Does What

## Split principle

The work is split **vertically by module, at a typed interface**, so neither
person waits on the other. The interfaces (`backend/app/contracts/`) and fakes
(`contracts/fakes.py`) already exist on `dev`, so both people can start on
day 1.

| | **Ronit: "Learner Intelligence"** | **Mit: "Explanation & Product"** |
|---|---|---|
| Patent modules | A (Unified Learner State), D (Re-Planner), C (update rules) | B (Explanation Generator), C (capture & summary) |
| Main skills | Probability/stats, Python, SQL, research | LLM/prompting, FastAPI, Next.js/React, DevOps |
| Owns | `db/`, `graph/`, `psychometrics/`, `learner_model/`, `planner/`, `content/` (except items), `research/` | `api/`, `auth/`, `explainer/`, `telemetry/`, `frontend/`, `content/items/`, CI/deploy |
| Detailed tasks | [`tasks/ronit.md`](../tasks/ronit.md) | [`tasks/mit.md`](../tasks/mit.md) |
| Branch | `ronit` | `mit` |

**The handshake between the two halves:**

- `ExplanationFeedbackSummary` (Mit produces it, Ronit consumes it)
- `StyleParams` + `Recommendation` (Ronit produces them, Mit consumes them)
- `LearnerState` (Ronit produces it, Mit displays it)

## If a third teammate joins

Create a branch with their name from `dev`, add `tasks/<name>.md`, and move
these tasks to them unchanged:

- **R6** (simulator), **R8** (pilot analysis + resonance/drift backtest)
- **M5** (item bank)
- **S5** (report/paper writing lead)

This gives a third lane, **"Research & Content"**, and lightens both existing
lanes. Update the owner columns in `ARCHITECTURE.md` in the same PR.

## Timeline (12 weeks)

| Week | Milestone | Ronit | Mit | Shared |
|---|---|---|---|---|
| 1 | **M0 Setup** | R0 DB + migrations; start R1 | M0 frontend scaffold + auth | S1 kickoff; **S4 ethics/consent request** |
| 2–3 | **M1 Walking skeleton**: the loop runs end-to-end on 3 concepts with real DB, template explanations, real BKT | R1 (first 3 concepts, then all), R2 BKT, R3 questionnaire | M1 API routes, M2 telemetry | Integration day every Friday |
| 4–6 | **M2 Full loop**: 60 concepts, precomputed Gemini variants, bandit, dashboard | R4 planner, R5 style choice + feedback updates | M3 explainer, M4 learning UI, M5 item bank, M6 dashboard | S3 review items and cards together |
| 7–8 | **M3 Validation & freeze**: simulator study, audit, deploy. `dev → main` = **v0.9** | R6 simulator, R7 hardening | M7 experiment infra, deploy, LLM audit | S2 pre-registration committed |
| 9–10 | **M4 Pilot** | Monitor data quality | M8 pilot operations & fixes | Run pilot (pre/post tests) |
| 11–12 | **M5 Analysis & delivery**. `dev → main` = **v1.0** | R8 analysis + backtest | M8 demo video, system write-up | S5 report/paper, patent update |

## Shared tasks (S)

- **S1 Kickoff (day 1, 1 h):** both read `PROJECT_BRIEF.md` and
  `CRITICAL_REVIEW.md`, agree on D1–D11, and fix the weekly sync times
  (suggested: Tue 15 min stand-up, Fri 1 h integration).
- **S2 Pre-registration (week 8):** write `research/preregistration.md` from
  `EVALUATION_PLAN.md`. Both sign off.
- **S3 Content review (weeks 3–6):** Ronit reviews items, Mit reviews concept
  cards. Each PR touching `content/` needs the other's approval.
- **S4 Ethics & consent (start week 1):** talk to your guide, draft the
  consent text (Mit puts it in the UI), and get approval before week 9.
- **S5 Write-up (weeks 11–12):**
  - Ronit: method, model, results.
  - Mit: system, implementation, UX, audit.
  - Also: update the patent draft using `CRITICAL_REVIEW.md` §2.6–2.7.

## Weekly integration ritual (every Friday)

1. Each person merges `dev` into their own branch and fixes conflicts.
2. Each person opens a PR to `dev` with the week's finished tasks.
3. The other person reviews: CI must be green and every acceptance check in
   the task file must be ticked.
4. Merge, then run the end-to-end smoke test (`backend/tests` + a manual
   click-through once the frontend exists).
5. Update the checkboxes in `tasks/*.md` and post a 3-line status in your
   team chat.

## Definition of done (every task)

- [ ] Code is in the owner's directories only (or a `contract` PR was approved)
- [ ] Unit tests for the logic; `pytest` and `ruff` pass locally and in CI
- [ ] Every acceptance check listed in the task is met
- [ ] Docs updated if behaviour changed (`MODEL_SPEC.md`, `API_CONTRACT.md`, etc.)
- [ ] Task checkbox ticked in `tasks/<name>.md` in the same PR
