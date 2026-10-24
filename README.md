# Psychometric Concept-Graph Explanation-Feedback Engine

Adaptive learning engine for Data Structures & Algorithms that combines a
**concept-mastery graph** with a **psychometric trait vector**, generates
**concept-level explanations shaped by that profile**, and uses the learner's
**interaction with each explanation** as a feedback signal that updates both.

## Branch model

| Branch  | Purpose                                                     | Who writes to it         |
|---------|-------------------------------------------------------------|--------------------------|
| `main`  | Stable, tested releases only (demo / submission builds)     | PR from `dev` only       |
| `dev`   | Integration branch: all code is combined and tested here    | PRs from `ronit` / `mit` |
| `ronit` | Ronit's working branch (learner model, planner, research)   | Ronit                    |
| `mit`   | Mit's working branch (explanations, telemetry, API, UI)     | Mit                      |

All project docs, agent instructions and code live on `dev`. Start there:
`git checkout dev` and read `AGENTS.md`.

## Start here

| If you are… | Read |
|---|---|
| Ronit or Mit (human) | `docs/TEAM_PLAN.md` → your `tasks/<name>.md` → `docs/GIT_WORKFLOW.md` |
| A coding agent | `AGENTS.md` (Claude Code loads it through `CLAUDE.md`) |
| A reviewer or guide | `docs/PROJECT_BRIEF.md`, `docs/CRITICAL_REVIEW.md`, `docs/EVALUATION_PLAN.md` |

| Doc | Contents |
|---|---|
| `docs/PROJECT_BRIEF.md` | Scope, the one claim to prove, design decisions D1–D11 |
| `docs/CRITICAL_REVIEW.md` | Honest rating, weak points, real-world performance analysis |
| `docs/ARCHITECTURE.md` | Modules, the closed loop, the ownership map |
| `docs/DATA_MODEL.md` · `docs/API_CONTRACT.md` | Tables and endpoints |
| `docs/MODEL_SPEC.md` | BKT, trait bandit, planner rules, resonance/drift math |
| `docs/EVALUATION_PLAN.md` | Hypotheses H1–H5, pilot protocol |
| `docs/TEAM_PLAN.md` · `docs/GIT_WORKFLOW.md` | Who does what, when, and how code flows to `main` |

## Quickstart

```bash
cp .env.example .env
docker compose up -d db
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q                         # includes the closed loop run through in-memory fakes
uvicorn app.main:app --reload     # http://localhost:8000/health
```
