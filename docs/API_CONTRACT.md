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
Browsers never hold the token: the web app's server forwards `/api/v1/*`
(`frontend/src/app/api/[...path]/route.ts`), takes the token out of the register and login
answers, and keeps it in an httpOnly, `SameSite=Strict` cookie (`pcg_session`, path `/api`) that
it turns back into the bearer header. Through the web app, register and login answer `{user}`.

**Ownership rule:** every learner resource (recommendation, explanation, events) is checked
against the caller. Another learner's id answers `404`, exactly like an id that does not exist.

| Method & path | Body → Response | Notes |
|---|---|---|
| `GET /health` | → `{status, version}` | Liveness; no `version` in production |
| `GET /health/ready` | → `{status}` or 503 | Readiness: the database answers |
| `POST /auth/register` | `{email, password, display_name}` → `{token, user}` | Assigns a balanced, random arm. Password 8–72 bytes. Unknown fields rejected (`is_admin`, `arm` cannot be set). `409` for a taken email; `403 REGISTRATION_CLOSED` when `ALLOW_REGISTRATION=false`; `429 TOO_MANY_REGISTRATIONS` after `REGISTER_MAX_PER_HOUR` attempts from one client (taken emails count too) |
| `POST /auth/login` | `{email, password}` → `{token, user}` | Same error for unknown email and wrong password. 5 failures per email (25 per client) in 15 min → `429 TOO_MANY_LOGIN_ATTEMPTS` |
| `POST /auth/logout` | → 204 | Revokes every token issued so far |
| `POST /auth/consent` | `{}` → `{consent_at}` | Learning routes return `403 CONSENT_REQUIRED` until this is called; recorded once |
| `GET /auth/me` | → `user` | Includes `is_admin` and `onboarded` (the questionnaire is done; the UI sends new users to onboarding until it is) |
| `DELETE /me` | → 204 | Withdraw: the account stops working now; `app.auth.purge` deletes it and its data |
| `GET /onboarding/questionnaire` | → `list[QuestionnaireItem]` | From `content/questionnaire.yaml` |
| `POST /onboarding/questionnaire` | `{answers: {item_id: 1..5}}` → `StateDelta` | Every item required. Taken once: a resubmission returns the first result |
| `POST /session/next` | `{}` → `NextStepResponse` | Planner → style → explainer. An unanswered recommendation is served again for 2 h (reloads, tabs, double clicks). Options are shuffled per learner; answers are never sent |
| `POST /attempts` | `AttemptIn` + required `recommendation_id` → `AttemptResult` + `change` (E5) | The item must be the recommendation's; one answer per recommendation (`409 ALREADY_ANSWERED`); MCQ answers must be an option. Graded on the server. Practice answers close the explanation's feedback loop (Module C); placement answers do not |
| `GET /explanations/{id}` | → `Explanation` | Own explanations only |
| `POST /explanations/{id}/events` | `{events: list[ExplanationEventIn]}` (1–100) → `{accepted, duplicates}` | Idempotent per `idempotency_key`. `followup_answered` is server-only. `clarity_rated` needs rating 1–5, `why_rated` needs `helpful` bool. Dwell is capped (10 min per stretch, 30 min total) |
| `POST /explanations/{id}/close` | `{}` → `ExplanationFeedbackSummary` + `change` (E5) | Called on "Continue". Idempotent: the second call returns the stored summary |
| `GET /recommendations/{id}/why` | → `RecommendationWhy` | XAI E1–E3 ("Why this?"), exactly as stored when the planner decided |
| `GET /recommendations/{id}/model` | → `ModelInsight` | The performance model's P(correct) for that question, from the features as they were when it was recommended. Includes the SHAP, LIME (with R²) and LRP attributions, DiCE counterfactuals, method agreement, notes, and `answered_correctly` once answered. Own recommendations only (404 otherwise); about 0.5 s the first time, then cached. CPU-heavy: see the limits below |
| `GET /model/card` | → model card | The model's training data, test metrics against BKT and logistic regression, global SHAP and LRP importance, and explanation-quality checks. Any signed-in user |
| `GET /learners/me/report` | → `UserReport` | The learner's report (XAI_DESIGN §8): profile radars, the XAI matrix (SHAP, LIME, LRP, direction, agreement per factor), method agreement, explanation quality (LIME R², SHAP/LRP completeness, DiCE validity/proximity/sparsity/diversity), a neutral summary, a disclaimer, and the data for the waterfall, decision plot, LRP heatmap and DiCE table. Each method runs on its own; `methods` lists any that failed. Own data only; cached until the next answer. CPU-heavy: see the limits below |
| `GET /admin/learners` | → `LearnerListing[]` | Admins only: learners by pseudonym (HMAC with `ANALYSIS_SALT`), arm, answers and last activity; never names or emails. 503 without a salt |
| `GET /admin/learners/{pseudonym}/report` | → `UserReport` | Admins only: one learner's report, by pseudonym; 404 for an unknown one |
| `GET /admin/xai/global` | → `GlobalAttributions` | Admins only: SHAP for recent predictions across learners (at most 60 learners × 8 answers), for the beeswarm; no identifiers. Cached for 10 minutes |
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
the counters are shared through Redis when `REDIS_URL` is set. The client is identified by, in
order: `X-Client-IP` when `X-Proxy-Secret` matches `PROXY_SECRET` (the web app's server naming
the browser); the last `X-Forwarded-For` hop, only with `TRUST_FORWARDED_FOR=true` and a request
from `TRUSTED_PROXY_IPS`; the connection's address. Every response, 413s and 429s included,
carries the security headers; production adds `Strict-Transport-Security`.

CPU-heavy endpoints (`/recommendations/{id}/model`, `/learners/me/report`,
`/admin/learners/{pseudonym}/report`, `/admin/xai/global`): at most `XAI_REQUESTS_PER_MINUTE` per
user (`429 TOO_MANY_EXPLANATION_REQUESTS`), at most `XAI_MAX_CONCURRENT` worked out at once, and up
to `XAI_MAX_WAITING` more wait up to `XAI_WAIT_SECONDS`; beyond that `503 SERVER_BUSY` with
`Retry-After: 5`. The web app retries a busy read up to three times, waiting 0.5–1.5 × Retry-After.
