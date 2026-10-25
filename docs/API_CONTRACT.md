# API Contract (v1)

Base path `/api/v1`. The routes call the domain services defined in
`backend/app/contracts/services.py` (real, database-backed implementations, wired per request in
`app/api/deps.py`). Request and response bodies are the Pydantic models in `backend/app/contracts/`
and `backend/app/api/schemas.py`. The generated OpenAPI document (`/openapi.json`, development
only) is the source of truth for the frontend client (`npm run gen:api`).

Errors always look like `{"error": {"code": "STRING_CODE", "message": "..."}}`. Unhandled errors
return `500 INTERNAL_ERROR` without details; validation errors return `422 VALIDATION_ERROR`.

Auth: `Authorization: Bearer <jwt>` on everything except `/health*`, `/auth/register` and
`/auth/login`. Tokens expire after `JWT_EXPIRE_HOURS` and are revoked by logout and withdrawal.

**Ownership rule:** every learner resource (recommendation, explanation, events) is checked
against the caller. Another learner's id answers `404`, exactly like an id that does not exist.

| Method & path | Body → Response | Notes |
|---|---|---|
| `GET /health` | → `{status, version}` | Liveness |
| `GET /health/ready` | → `{status}` or 503 | Readiness: the database answers |
| `POST /auth/register` | `{email, password, display_name}` → `{token, user}` | Assigns a balanced, random arm. Password 8–72 bytes. Unknown fields rejected (`is_admin`, `arm` cannot be set) |
| `POST /auth/login` | `{email, password}` → `{token, user}` | Same error for unknown email and wrong password. 5 failures per email (25 per client) in 15 min → `429 TOO_MANY_LOGIN_ATTEMPTS` |
| `POST /auth/logout` | → 204 | Revokes every token issued so far |
| `POST /auth/consent` | `{}` → `{consent_at}` | Learning routes return `403 CONSENT_REQUIRED` until this is called; recorded once |
| `GET /auth/me` | → `user` | Includes `is_admin` |
| `DELETE /me` | → 204 | Withdraw: the account stops working now; `app.auth.purge` deletes it and its data |
| `GET /onboarding/questionnaire` | → `list[QuestionnaireItem]` | From `content/questionnaire.yaml` |
| `POST /onboarding/questionnaire` | `{answers: {item_id: 1..5}}` → `StateDelta` | Every item required. Taken once: a resubmission returns the first result |
| `POST /session/next` | `{}` → `NextStepResponse` | Planner → style → explainer. An unanswered recommendation is served again for 2 h (reloads, tabs, double clicks). Options are shuffled per learner; answers are never sent |
| `POST /attempts` | `AttemptIn` + required `recommendation_id` → `AttemptResult` + `change` (E5) | The item must be the recommendation's; one answer per recommendation (`409 ALREADY_ANSWERED`); MCQ answers must be an option. Graded on the server. Practice answers close the explanation's feedback loop (Module C); placement answers do not |
| `GET /explanations/{id}` | → `Explanation` | Own explanations only |
| `POST /explanations/{id}/events` | `{events: list[ExplanationEventIn]}` (1–100) → `{accepted, duplicates}` | Idempotent per `idempotency_key`. `followup_answered` is server-only. `clarity_rated` needs rating 1–5, `why_rated` needs `helpful` bool. Dwell is capped (10 min per stretch, 30 min total) |
| `POST /explanations/{id}/close` | `{}` → `ExplanationFeedbackSummary` + `change` (E5) | Called on "Continue". Idempotent: the second call returns the stored summary |
| `GET /recommendations/{id}/why` | → `RecommendationWhy` | XAI E1–E3 ("Why this?"), exactly as stored when the planner decided |
| `GET /learners/me/state` | → `LearnerState` | Open learner model |
| `GET /learners/me/history?limit=&before_id=` | → `list[StateUpdateView]` | Newest first, at most 200 per page |
| `GET /learners/me/explain?subject=` | → `BeliefExplanation` | XAI E4. `subject` = concept id or trait name |
| `GET /graph` | → `{concepts, edges}` | |
| `GET /tests/{pretest\|posttest}` | → `{phase, items, submitted}` | No answers |
| `POST /tests/{pretest\|posttest}` | `{answers: {item_id: response}}` → `{phase, answered}` | Once per test; post-test only after the pre-test. Stored with `record_test_attempt` (never changes the model); no score is returned |
| `GET /admin/metrics` | → `AdminMetricsResponse` | Admin only. Measured from the database |
| `GET /admin/export.csv?table=users\|assignments\|attempts` | → CSV | Admin only. Salted pseudonyms (`ANALYSIS_SALT`, same as `research/analysis`); `503 EXPORT_DISABLED` without a salt |
| `GET /ops/status` | → `OpsHealthResponse` | Admin only |

`NextStepResponse` (defined in `contracts/planning.py`):

```json
{
  "recommendation": { "...": "Recommendation" },
  "explanation":    { "...": "Explanation" },
  "item":           { "...": "Item (answer field removed, options shuffled)" }
}
```

Transport: CORS allows only `CORS_ORIGINS`; request bodies over 64 KB get `413`; responses carry
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and (for `/api/*`) `Cache-Control:
no-store`. Requests are rate limited per client (`RATE_LIMIT_REQUESTS_PER_MINUTE`);
`X-Forwarded-For` is trusted only with `TRUST_FORWARDED_FOR=true`.
