# Architecture

## Component view

```mermaid
flowchart TB
  subgraph FE["frontend/ (Next.js) — Mit"]
    UI[Learning session UI]
    TEL[useExplanationTelemetry hook]
    OLM[Learner dashboard / open learner model]
    ADM[Admin & research page]
  end

  subgraph API["backend/app/api — Mit"]
    R1[/auth, onboarding/]
    R2[/session/next, attempts/]
    R3[/explanations/:id/events/]
    R4[/learners/me/state, admin/]
  end

  subgraph CORE["Domain services (Python Protocols in app/contracts/services.py)"]
    LM["learner_model (A) — Ronit<br/>BKT mastery, traits, affect"]
    PL["planner (D) — Ronit<br/>next step + reasons + style choice"]
    EX["explainer (B) — Mit<br/>precomputed → LLM → template"]
    FA["telemetry (C, capture) — Mit<br/>events → FeedbackSummary"]
    GR["graph + psychometrics — Ronit<br/>concepts, edges, questionnaire"]
  end

  DB[(PostgreSQL)]
  LLM[[Gemini API]]

  UI --> R2 --> PL
  PL --> LM
  R2 --> EX --> LLM
  TEL --> R3 --> FA -->|ExplanationFeedbackSummary| LM
  OLM --> R4 --> LM
  LM --> DB
  EX --> DB
  FA --> DB
  GR --> DB
```

## The closed loop, step by step

```mermaid
sequenceDiagram
  autonumber
  actor L as Learner
  participant UI as Frontend (Mit)
  participant API as API (Mit)
  participant PL as Planner (Ronit)
  participant LM as LearnerModel (Ronit)
  participant EX as Explainer (Mit)
  participant FA as Telemetry/Analyzer (Mit)

  L->>UI: open session
  UI->>API: POST /session/next
  API->>LM: get_state(user)
  API->>PL: next_step(state)
  PL-->>API: Recommendation (+ reasons)
  API->>PL: choose_style(state)
  PL-->>API: StyleParams, style_source
  API->>EX: explain(ExplanationRequest)
  EX-->>API: Explanation (precomputed | llm | template)
  API-->>UI: recommendation + explanation + item
  L->>UI: reads, expands, rates clarity
  UI->>API: POST /explanations/{id}/events (batched, idempotent)
  L->>UI: answers micro-check / item
  UI->>API: POST /attempts
  API->>LM: apply_attempt(...)  → mastery update (BKT)
  API->>FA: summarize(explanation_id)
  FA-->>API: ExplanationFeedbackSummary
  API->>LM: apply_explanation_feedback(summary) → trait + misconception update
  Note over LM: next /session/next uses the updated state → loop closed
```

## Ownership boundaries

Each person owns the directories listed for them, and only the owner edits
them. To change something you don't own, open an issue or ask the owner. The
owner reviews every PR to `dev` that touches their area.

| Path | Owner |
|---|---|
| `backend/app/contracts/` | **Shared.** Changes only through a PR labelled `contract`, approved by both. |
| `backend/app/db/`, `backend/alembic/` | Ronit |
| `backend/app/graph/`, `backend/app/psychometrics/`, `backend/app/learner_model/`, `backend/app/planner/` | Ronit |
| `content/` (concept graph, concept cards, misconceptions, questionnaire) | Ronit |
| `content/items/` (item bank) | Mit (both review) |
| `research/` | Ronit |
| `backend/app/api/`, `backend/app/explainer/`, `backend/app/telemetry/`, `backend/app/auth/` | Mit |
| `frontend/` | Mit |
| `.github/`, `docker-compose.yml`, deploy config | Mit. Ronit adds the Postgres service to CI in task R0. |
| `docs/`, `AGENTS.md`, `tasks/` | Shared. Update your own task file freely. |

## How services connect

- `app/contracts/services.py` defines one Protocol per service.
  `app/contracts/fakes.py` has in-memory fakes, so each person can build
  against the other's interface before the real code exists.
- The API layer gets services through FastAPI dependencies in
  `app/api/deps.py`, which Mit creates in M1. Swapping a fake for the real
  implementation is a one-line change there.
- Database access goes through repository functions in `app/db/`, owned by
  Ronit. Mit's packages (explainer, telemetry) define their own tables in
  `DATA_MODEL.md`. Ronit writes the initial migration for **all** tables in
  R0. After that, each owner adds migrations for their own tables: rebase onto
  `dev` first so Alembic has a single head.

## Latency budget (p95)

| Call | Budget | How |
|---|---|---|
| `POST /session/next` | 300 ms | State in a single query; precomputed explanation |
| `POST /attempts` | 200 ms | BKT is O(1); feedback update runs as a background task |
| `POST /explanations/{id}/events` | 100 ms | Append-only insert with an idempotency key |
| Live LLM fallback | 4 s timeout | After the timeout, the template fallback is used |
