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
| `POST /auth/consent` | `{}` → `{consent_at}` | — | Learning routes return 403 `CONSENT_REQUIRED` until this is called |
| `DELETE /me` | → 204 | — | Soft delete; a purge job removes the data |
| `GET /onboarding/questionnaire` | → `list[QuestionnaireItem]` | psychometrics | |
| `POST /onboarding/questionnaire` | `{answers: {item_id: 1..5}}` → `StateDelta` | `LearnerModelService.init_from_questionnaire` | |
| `POST /session/next` | `{}` → `NextStepResponse` | `get_state` → `PlannerService.next_step` → `choose_style` → `ExplainerService.explain` | Starts with a diagnostic phase for new learners |
| `POST /attempts` | `AttemptIn` → `AttemptResult` | `LearnerModelService.apply_attempt`; if `explanation_id` is set, also `FeedbackAnalyzer.summarize` → `apply_explanation_feedback` (background task) | |
| `GET /explanations/{id}` | → `Explanation` | — | |
| `POST /explanations/{id}/events` | `{events: list[ExplanationEventIn]}` → `{accepted:int, duplicates:int}` | telemetry | Idempotent per `idempotency_key` |
| `POST /explanations/{id}/close` | `{}` → `ExplanationFeedbackSummary` | `summarize` → `apply_explanation_feedback` | Called when the card is dismissed without a micro-check |
| `GET /learners/me/state` | → `LearnerState` | `get_state` | For the dashboard (open learner model) |
| `GET /learners/me/history` | → `list[StateUpdateView]` | db | "Why we think this" |
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
