# Mit: Explanation & Product Lane

> **For the coding agent:** you are working for **Mit**. Read `AGENTS.md`
> first. Work only on the `mit` branch (or `mit/<task>` sub-branches). Pick
> the **first unchecked task whose dependencies are done**, plan it,
> implement it, test it, tick its box in this file, and prepare a PR to
> `dev`. Do not edit Ronit's directories (see `docs/ARCHITECTURE.md`
> ownership). Until Ronit's real services are merged, use the fakes in
> `backend/app/contracts/fakes.py`. If you need something from Ronit's side,
> add a note under "Asks for Ronit" at the bottom of this file.

**You own:**
- `backend/app/api/`, `backend/app/auth/`, `backend/app/explainer/`,
  `backend/app/telemetry/`
- `frontend/`
- `content/items/`
- `.github/`, `docker-compose.yml`, deploy config

**You implement these Protocols** from `backend/app/contracts/services.py`:
`ExplainerService`, `FeedbackAnalyzer`. You also implement every HTTP route in
`docs/API_CONTRACT.md`.

**Key references:** `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`
(tables `users`, `experiment_assignments`, `items`, `explanation_*`),
`docs/PROJECT_BRIEF.md` D5/D6/D9/D11, and `docs/EVALUATION_PLAN.md`
(system quality).

---

## M0: Frontend scaffold + auth (week 1)
- **Depends on:** nothing (auth persistence needs R0; use an in-memory store
  until then)
- **Do:**
  1. `frontend/`: Next.js (App Router, TypeScript, Tailwind, ESLint). Set up a
     typed API client generated from the backend's `/openapi.json` with
     `openapi-typescript` (`npm run gen:api`).
  2. `backend/app/auth/`: email + password register/login (bcrypt or argon2),
     JWT, a `current_user` dependency, a consent endpoint, and arm assignment
     at register (balanced: the arm with the fewest users, ties broken at
     random).
  3. Extend the CI frontend job (it runs automatically once
     `frontend/package.json` exists): `npm ci && npm run lint && npm run build`.
- **Acceptance:**
  - [x] Register → login → consent works through the API (tests with httpx)
  - [x] The frontend builds in CI; the login page works against a local
        backend
- [x] **M0 done**

## M1: API layer (weeks 2–3)
- **Depends on:** M0
- **Do:** every route in `docs/API_CONTRACT.md`, under `backend/app/api/`
  with one router per area. Add `api/deps.py`, which provides service
  instances (fakes now, real implementations later: one line to switch per
  service). Include the uniform error format, the consent guard, and
  background tasks for feedback application. `/session/next` follows the
  sequence diagram in `ARCHITECTURE.md` exactly.
- **Acceptance:**
  - [x] An API test runs the whole loop with fakes: register → consent →
        questionnaire → next → events → attempt (micro-check) → state changed
  - [x] OpenAPI includes every contract model
- [x] **M1 done**

## M2: Explanation telemetry (Module C capture) (weeks 2–3)
- **Depends on:** M0 (frontend), M1 (route)
- **Do:**
  1. Frontend hook `useExplanationTelemetry(explanationId)`:
     - IntersectionObserver + Page Visibility API, so dwell counts **only
       visible time**;
     - events for shown/expanded/collapsed/replayed/hidden/visible/
       clarity_rated/dismissed;
     - a UUID idempotency key per event;
     - batches sent every 5 s and on `pagehide` (`navigator.sendBeacon`), with
       a localStorage retry queue.
  2. Backend: ingest with dedupe on `idempotency_key`, and
     `FeedbackAnalyzer.summarize(explanation_id)` → `ExplanationFeedbackSummary`
     (effective dwell, expanded, replays, clarity, followup_correct,
     dismissed_quickly = visible for < 3 s with no other interaction). Store
     it in `explanation_feedback`.
  3. Clarity prompt: one tap, shown on about 1 in 3 explanations (random,
     logged), never blocking.
- **Acceptance:**
  - [x] Unit tests for summarize on hand-made event sequences (tab hidden
        mid-read, duplicates, out-of-order client timestamps)
  - [x] Sending the same batch twice reports `duplicates == n`
- [x] **M2 done**

## M3: Explainer (Module B) (weeks 3–5)
- **Depends on:** R1a (3 concept cards) for real grounding; use the example
  card until then
- **Do:** `backend/app/explainer/`, implementing `ExplainerService.explain`.
  1. **Prompt builder:** inputs are the concept card(s), the
     `ReasonEvidence`, and `StyleParams` (example_first, length, depth). The
     prompt instructs the model to use **only** facts from the card. Output
     is JSON `{body_markdown, concept_ids_mentioned}`, using the Gemini
     structured-output schema. Version every prompt (`prompt_version`).
  2. **Validator:** concept IDs ⊆ request, word count within the bucket
     (short ≤ 80, medium ≤ 160, long ≤ 300), no code blocks unless the card
     has them, and a `validation` JSON recording the results.
  3. **Template fallback** (Jinja), built from the card fields. It always
     works and never needs the network.
  4. **Wrapper:** reason sentence ("Why this: …", from `ReasonEvidence`), tone
     sentence, and diagram toggle. These are added on top of the variant body
     and are not generated by the LLM.
  5. **Precompute CLI:** `python -m app.explainer.precompute --concepts all`
     generates 12 variants per concept (example_first × length × depth) into
     `explanation_variants`, with rate limiting and resume support.
  6. **Runtime order:** approved/auto_ok variant → live LLM (4 s timeout) →
     template. Record `source` and `latency_ms`.
  7. Model names come from `.env` (`GEMINI_MODEL_EXPLAIN`). Never hard-code
     them.
- **Acceptance:**
  - [x] Tests with a mocked Gemini client: valid output passes, an invalid
        concept ID triggers the fallback, a timeout triggers the fallback
  - [x] The precompute run for 3 concepts produces 36 rows
  - [x] Runtime p95 < 50 ms when a variant exists
- [x] **M3 done**

## M4: Learning UI (weeks 3–5)
- **Depends on:** M1, M2
- **Do:** pages for onboarding (consent text from S4 → questionnaire →
  diagnostic intro), the **session** (item card → answer → correct/incorrect
  feedback → explanation card with a "Why this?" reasons panel → micro-check
  → next), and loading/fallback states. Make it keyboard-accessible and
  responsive.
- **Acceptance:**
  - [ ] Playwright smoke test: a new user completes onboarding and 3 items
- [ ] **M4 done**

## M5: Item bank (weeks 4–6)
- **Depends on:** R1b (concepts + misconceptions)
- **Do:** a generation script (Gemini) for ≥3 items per concept: MCQ with
  each distractor mapped to a misconception, plus 1 micro-check per concept.
  Items are saved as `draft` in `content/items/*.yaml`. Add a review flow
  (YAML diff review in the PR is fine, or a small admin page). **Ronit
  reviews and approves** (S3). Also build the 15-item pre-test and its
  parallel post-test (not used in sessions).
- **Acceptance:**
  - [ ] ≥180 approved items; every concept has ≥1 approved micro-check
  - [ ] A test checks that answers are among the options and that every
        distractor maps to a real misconception
- [ ] **M5 done**

## M6: Dashboards (weeks 5–6)
- **Depends on:** M1; R2 for real data
- **Do:**
  1. **Learner dashboard (open learner model):**
     - the concept graph (React Flow or Cytoscape), coloured by mastery, with
       an uncertainty ring;
     - traits in plain language ("You seem to learn best from examples
       first: moderately confident"), never as scary labels;
     - "why we think this" from `/learners/me/history`.
  2. **Admin page:** users per arm, sessions, p50/p95 latency, explanation
     source mix, clarity distribution, and CSV export.
- **Acceptance:**
  - [ ] Dashboards render for the demo-seed learners
- [ ] **M6 done**

## M7: Experiment infra, deploy, audit (weeks 6–8)
- **Depends on:** M1–M4
- **Do:**
  - Feature flags per arm (generic / static / closed_loop) passed to the
    services.
  - Deploy:
    - backend → Render, Railway or Fly;
    - Postgres → Neon or Supabase;
    - frontend → Vercel.
    Secrets go in the platform env, never in git.
  - Rate limiting, the `DELETE /me` purge job, and pseudonymised exports.
  - **LLM audit:** export 100 random shown explanations; both of you rate
    them; compute κ; write `research/reports/llm_audit.md`.
- **Acceptance:**
  - [ ] The production URL works end-to-end
  - [ ] The audit is done; fix the prompt if the wrong rate is ≥ 2%
- [ ] **M7 done**

## M8: Pilot ops & delivery (weeks 9–12)
- **Do:** onboard the students, watch error logs and dashboards every day,
  ship hotfixes (PR → dev → main hotfix), record a demo video, and write the
  system/implementation chapter.
- [ ] **M8 done**

---

## Asks for Ronit
_(add items here when you need something from Ronit's side)_

## Notes / decisions log
_(date: decision, and why)_
