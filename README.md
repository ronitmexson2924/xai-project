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

## Run the whole app with one command

Needs only Docker (Docker Desktop on Mac/Windows):

```bash
docker compose up --build
```

Then open **http://localhost:3000**. The first build takes a few minutes; later starts take
seconds. Compose starts Postgres, the API (http://localhost:8000, docs at `/docs`) and the
frontend. On every start it migrates the database and loads `content/`. The first time, it also
creates these accounts:

| Account | Password | What you see |
|---|---|---|
| Sign up yourself | your choice | the new-student flow: consent, questionnaire, dashboard |
| `asha@demo.example.com` | `Demo-pass-1` | a new learner |
| `ben@demo.example.com` | `Demo-pass-1` | a misconception being fixed |
| `chen@demo.example.com` | `Demo-pass-1` | an advanced learner with tuned explanations |
| `admin@example.com` | `Admin-pass-1` | the study admin page |

Your data survives restarts (`docker compose down`, then `up`). `docker compose down -v` wipes
it. For live LLM explanations, put `GEMINI_API_KEY` and the `GEMINI_MODEL_*` names in `.env`;
without them, explanations come from the reviewed templates. This setup is for local use and
demos only: it uses fixed development secrets and serves draft items. Production deploys with
`render.yaml` and Vercel (see Deploy).

## Quickstart (for development, with hot reload)

```bash
cp .env.example .env
docker compose up -d db                      # Postgres on 5432

cd backend && python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head                         # schema
python -m app.graph.seed ../content          # concepts, misconceptions, items, questionnaire
python -m app.graph.demo_seed --password 'Demo-pass-1'   # optional: asha|ben|chen@demo.example.com
python -m app.auth.onboard admin --email you@example.com # an admin for /admin (asks a password)
INCLUDE_DRAFT_ITEMS=true uvicorn app.main:app --reload   # drafts until the bank is reviewed (S3)

cd ../frontend && npm ci && npm run dev      # http://localhost:3000
```

### The app

`/` landing page → `/signup` or `/login` → new learners go through `/onboarding` (study consent,
then the 20-statement questionnaire) → `/dashboard` (next step, concept map, how explanations adapt,
recent activity). Learning happens in `/session`, the study tests in `/tests`, account and
withdrawal in `/account`, and study admins see `/admin`. Light and dark themes follow the system
setting, and animations respect "reduce motion".

## Checks

```bash
cd backend && ruff check . && ruff format --check . && pytest -q   # unit, API and security tests
cd frontend && npm run lint && npm run build
cd frontend && PYTHON=../backend/.venv/bin/python npx playwright test   # browser E2E on a fresh pcg_e2e DB
```

`backend/tests/test_security.py` and `frontend/tests/abuse.spec.ts` attack the app the way a
hostile user would (forged tokens, other learners' ids, replays, injection, oversized input, ...).

## Deploy

- **API + Postgres:** `render.yaml` (Render blueprint). Runs as `ENVIRONMENT=production`, which
  refuses to start with a weak `JWT_SECRET` or `CORS_ORIGINS=*`; migrations and content seeding
  run on start. Set `CORS_ORIGINS` to the frontend URL and the Gemini variables in the dashboard.
- **Frontend:** Vercel (`frontend/vercel.json`) with `NEXT_PUBLIC_API_URL` set to the API URL.
- **Pilot accounts:** `python -m app.auth.onboard cohort --count 45 --output-csv pilot.roster.csv`
  (the roster holds passwords: `*.roster.csv` is git-ignored; delete it after hand-out).
- **Items:** only `approved` items are served. The bank (`content/items/`) is all `draft` until
  reviewed; `INCLUDE_DRAFT_ITEMS=true` serves drafts for demos and is refused in production.
- **Withdrawals:** run `python -m app.auth.purge` on a schedule to delete withdrawn accounts.
