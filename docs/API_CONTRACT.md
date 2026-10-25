# API Contract (v1)

Base path `/api/v1`. Mit implements the routes. They call the domain services
defined in `backend/app/contracts/services.py`. The request and response
bodies are the Pydantic models in `backend/app/contracts/`. The generated
OpenAPI document (`/openapi.json`) is the source of truth for the frontend
client.

Errors always look like `{"error": {"code": "STRING_CODE", "message": "..."}}`.

Auth: `Authorization: Bearer <jwt>` on everything except `/health` and
`/auth/*`.

| Method & path | Body → Response | Calls | Notes |
|---|---|---|---|
| `GET /health` | → `{"status":"ok","version":str}` | none | Exists already |
| `POST /auth/register` | `{email,password,display_name}` → `{token, user}` | — | Assigns the experiment arm |
| `POST /auth/login` | `{email,password}` → `{token, user}` | — | |
| `GET /auth/me` | → `UserResponse` | — | Includes `is_admin` and `questionnaire_done` |
| `POST /auth/consent` | `{}` → `{consent_at}` | — | Learning routes return 403 `CONSENT_REQUIRED` until this is called |
| `DELETE /me` | → 204 | — | Soft delete; a purge job removes the data |
| `GET /onboarding/questionnaire` | → `list[QuestionnaireItem]` | psychometrics | |
| `POST /onboarding/questionnaire` | `{answers: {item_id: 1..5}}` → `StateDelta` | `LearnerModelService.init_from_questionnaire` | |
| `POST /session/next` | `{}` → `NextStepResponse` | `get_state` → `PlannerService.next_step` → `choose_style` → `ExplainerService.explain` | Starts with a diagnostic phase for new learners |
| `POST /attempts` | `AttemptIn` → `AttemptResult` | `LearnerModelService.apply_attempt`; if `explanation_id` is set, also `FeedbackAnalyzer.summarize` → `apply_explanation_feedback` (background task) | |
| `GET /items/{id}` | → `PublicItem` | — | Only items already served to the caller (404 otherwise), answer removed |
| `GET /tests/{phase}` | → `list[PublicItem]` | graph | `phase` = `pretest` or `posttest`; answers go to `POST /attempts` with no recommendation |
| `GET /explanations/{id}` | → `Explanation` | — | |
| `POST /explanations/{id}/events` | `{events: list[ExplanationEventIn]}` → `{accepted:int, duplicates:int}` | telemetry | Idempotent per `idempotency_key` |
| `POST /explanations/{id}/close` | `{}` → `ExplanationFeedbackSummary` | `summarize` → `apply_explanation_feedback` | Called when the card is dismissed without a micro-check |
| `GET /learners/me/state` | → `LearnerState` | `get_state` | For the dashboard (open learner model) |
| `GET /learners/me/history` | → `list[StateUpdateView]` | db | "Why we think this" |
| `GET /recommendations/{id}/why` | → `RecommendationWhy` | `ExplainabilityService.why` | XAI E1–E3 ("Why this?" panel). The rationale was stored when the planner decided |
| `GET /learners/me/explain?subject=` | → `BeliefExplanation` | `ExplainabilityService.explain_belief` | XAI E4. `subject` = concept id or trait name |
| `GET /graph` | → `{concepts: list[Concept], edges: list[ConceptEdge]}` | graph | |
| `GET /admin/metrics` | → metrics JSON | — | Admin role only |
| `GET /admin/export.csv?table=...` | → CSV | — | Pseudonymised user IDs |

`NextStepResponse` (defined in `contracts/planning.py`):

```json
{
  "recommendation": { "...": "Recommendation" },
  "explanation":    { "...": "Explanation" },
  "item":           { "...": "Item (answer field removed)" }
}
```

XAI E5: after `apply_attempt` / `apply_explanation_feedback`, call
`ExplainabilityService.explain_change(delta)` and return the `ChangeNotice` with the response, so
the UI can show what the answer or rating changed. See `docs/XAI_DESIGN.md`.

## Behaviour the routes enforce

Added with the database-backed implementation (M1/M9/M10). Every case below has a test in
`backend/tests/test_api_security.py` or `frontend/tests/abuse.spec.ts`.

- `AttemptResult` also carries `change` and `feedback_change` (`ChangeNotice | null`, XAI E5).
- `POST /session/next` returns 409 `QUESTIONNAIRE_REQUIRED` before onboarding and 409
  `NO_CONTENT` when no reviewed item is available. An unanswered step younger than two hours
  is served again, so reloading does not skip a question.
- `POST /attempts` accepts only an item the server served to this learner: 422 `ITEM_NOT_SERVED`,
  `ITEM_MISMATCH` or `AMBIGUOUS_ATTEMPT` otherwise, and 409 `ALREADY_ANSWERED` for a replay.
  Multiple-choice answers must be one of the options; latency is clamped to one hour.
- Other learners' explanations, recommendations and items answer 404, never 403, so ids cannot be
  probed.
- Login and register are limited per account (`AUTH_RATE_LIMIT_PER_MINUTE`) and per client
  (`AUTH_IP_RATE_LIMIT_PER_MINUTE`); everything else per client. 429 carries `Retry-After`.
  `X-Forwarded-For` is ignored unless `TRUST_PROXY_HEADERS` is set.
- Bodies over 256 KB get 413. Unexpected errors get 500 `INTERNAL_ERROR` with no internals.
- `DELETE /me` erases name and email at once; `python -m app.auth.purge` removes the rest after
  the retention period.
- CSV exports pseudonymise user ids with a keyed hash (`EXPORT_SALT`) and neutralise cells that
  a spreadsheet would run as formulas.
