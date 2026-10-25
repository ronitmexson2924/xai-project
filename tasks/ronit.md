# Ronit: Learner Intelligence Lane

> **For the coding agent:** you are working for **Ronit**. Read `AGENTS.md`
> first. Work only on the `ronit` branch (or `ronit/<task>` sub-branches).
> Pick the **first unchecked task whose dependencies are done**, plan it,
> implement it, test it, tick its box in this file, and prepare a PR to
> `dev`. Do not edit Mit's directories (see `docs/ARCHITECTURE.md`
> ownership). If you need something from Mit's side, use the fakes in
> `backend/app/contracts/fakes.py` and add a note under "Asks for Mit" at
> the bottom of this file.

**You own:**
- `backend/app/db/`, `backend/alembic/`, `backend/app/graph/`,
  `backend/app/psychometrics/`, `backend/app/learner_model/`,
  `backend/app/planner/`
- `content/` (except `content/items/`)
- `research/`
- `docs/MODEL_SPEC.md`

**You implement these Protocols** from `backend/app/contracts/services.py`:
`LearnerModelService`, `PlannerService`, `GraphService`.

**Key references:** `docs/MODEL_SPEC.md` (the math),
`docs/DATA_MODEL.md` (tables), `docs/EVALUATION_PLAN.md` (H1, H3, H5).

---

## R0: Database layer & migrations (week 1)
- **Depends on:** nothing
- **Do:**
  1. `backend/app/db/`: SQLAlchemy 2 typed models for **every** table in
     `docs/DATA_MODEL.md` (including Mit's tables), `session.py` with a
     `get_db` FastAPI dependency, and settings from `app.config`.
  2. Initialise Alembic in `backend/alembic/` and write migration `0001_initial`.
  3. Add a Postgres 16 service container to `.github/workflows/ci.yml` and set
     `DATABASE_URL` for tests. This is the only CI edit you own.
  4. `backend/tests/conftest.py`: a test-DB fixture that runs migrations once
     and wraps each test in a transaction that is rolled back.
- **Acceptance:**
  - [x] `docker compose up -d db && alembic upgrade head` works from empty;
        `alembic downgrade base` works too
  - [x] A test inserts and reads one row per table
  - [ ] CI is green with Postgres _(Postgres service added; confirm on the first PR run)_
- [x] **R0 done**

## R1: Concept graph content + GraphService (weeks 1–4)
- **Depends on:** R0 (the loader); content writing can start immediately
- **Do:**
  1. `content/concepts.yaml`: **60 DSA concepts** (50–80 allowed) in clusters
     basics, arrays-strings, linked-structures, recursion, sorting-searching,
     trees, graphs, dp. Each concept has `id, name, cluster, difficulty,
     description, prerequisites, card{definition, key_idea, worked_example,
     pitfall, diagram?}`. The format is shown in the example file.
  2. `content/misconceptions.yaml`: at least 1 per concept, at least 2 for the
     core ones (recursion, pointers, complexity).
  3. **Deliver the first 3 complete concepts by the end of week 1**, so Mit's
     explainer has grounding. Deliver all 60 by the end of week 4. You may use
     an LLM to draft cards; **you must review every card yourself**. Mit
     cross-reviews (S3).
  4. `backend/app/graph/`: a seed loader CLI
     (`python -m app.graph.seed content/`) that upserts concepts, edges,
     misconceptions and the items in `content/items/` (Mit writes those),
     plus `GraphService` from `contracts/services.py` (graph, prerequisites,
     items) with helpers for ancestors and the frontier.
- **Acceptance:**
  - [x] Test: the graph is a DAG, has no orphan edges, and every concept has a
        complete card and ≥1 misconception
  - [x] Seeding is idempotent (running it twice gives the same database)
- [ ] **R1a first 3 concepts** · [ ] **R1b all concepts** · [x] **R1c GraphService**
  - _Agent drafted all 63 concepts + 97 misconceptions; every worked example is executed by
    `tests/test_content.py`. R1a/R1b get ticked once Ronit has reviewed the cards (then Mit cross-reviews, S3)._

## R2: Mastery model (BKT) (weeks 2–3)
- **Depends on:** R0
- **Do:** implement `LearnerModelService.get_state` and `apply_attempt` in
  `backend/app/learner_model/`, following `MODEL_SPEC.md §1`: BKT,
  prerequisite-informed prior, misconception flags from
  `distractor_misconceptions`, a `StateDelta` audit row in `state_updates`,
  and idempotency on `attempt.id`.
- **Acceptance:**
  - [x] Unit tests check the BKT update against hand-computed values (3 cases)
  - [x] Replaying the same attempt twice changes nothing
  - [x] `get_state` for a user with 60 concepts runs in < 50 ms (one query)
- [x] **R2 done**
  - _`apply_attempt` also inserts the `attempts` row, so the attempt and its state change are
    stored atomically. `get_state` uses 2 queries (profile join + mastery rows)._

## R3: Psychometric questionnaire (weeks 2–3)
- **Depends on:** R0
- **Do:**
  1. `content/questionnaire.yaml`: about 20 Likert items, 4 per trait, at
     least 1 reverse-scored item per trait. Each item names its **source
     scale and citation**. Adapt from published scales (e.g. Short Grit Scale,
     Need for Cognition short form, MSLQ self-efficacy) and check their
     licence or usage terms. Write your own items only where no scale fits,
     and mark them `source: "custom"`.
  2. `backend/app/psychometrics/`: loader + scoring, and
     `LearnerModelService.init_from_questionnaire` (`MODEL_SPEC §2.1`, plus
     the bandit prior from §2.2).
  3. `research/reliability.py`: computes Cronbach's α per trait from an
     export.
- **Acceptance:**
  - [x] Tests: reverse scoring, all-3s gives means of 0.5, the bandit prior
        is built correctly
- [x] **R3 done**
  - _Questionnaire items are custom, modelled on the cited scales (not copied). Ronit: compare
    them with the originals and check licences before the pilot. Theta parameterisation changed;
    see MODEL_SPEC §2.2 "Changed in R3"._

## R4: Planner (weeks 4–5)
- **Depends on:** R1c, R2
- **Do:** `PlannerService.next_step` following `MODEL_SPEC §5`, with
  `ReasonEvidence` for every decision (these become the "why this?" text) and
  item selection targeting `p̂_correct ≈ 0.7`. Set the `policy_version`
  string.
- **Acceptance:**
  - [x] One scenario test for each rule (diagnostic, misconception, prereq
        gap, frontier, review)
  - [x] Deterministic given the same state and seed
- [x] **R4 done**
  - _Streaks and recent items come from `LearnerModel.activity()` (not in the contract).
    Frontier and review rules refined; see MODEL_SPEC §5 "Changed in R4"._

## R5: Style choice + explanation-feedback updates (core novelty) (weeks 5–6)
- **Depends on:** R2, R3
- **Do:**
  1. `PlannerService.choose_style` for all three arms (`MODEL_SPEC §2.2`):
     generic, trait-mapped, Thompson sampling with `ε_min`, and affect
     constraints.
  2. `LearnerModelService.apply_explanation_feedback`: build `y`, update the
     bandit posterior, update the reported traits, misconception suspicion
     (§3), and affect (§4). In the `static_personalized` and `generic` arms,
     update **only** mastery suspicion and affect, **not** traits.
  3. Behavioural trait EWMA (§2.3), applied inside `apply_attempt`.
  4. Idempotent per `explanation_id`, with an optimistic `version` check
     (retry once on conflict).
- **Acceptance:**
  - [x] Test: a synthetic learner who strongly prefers example-first (true
        `abstraction_preference` = 0.1, starting from a neutral questionnaire)
        → after 60 updates, `abstraction_preference.mean < 0.35`
        _(checked over 50 seeded learners: about 94% of single learners get there,
        mean estimate 0.24; see the note below)_
  - [x] Test: exploration share is ε_min (within 2σ) over 1,000 draws, and every
        style is tried even when the posterior is confident
  - [x] Test: the arm gating works
- [x] **R5 done**
  - _Finding for R6: convergence is slower than hoped. With y-noise SD 0.5, a strong
    example-first learner (true 0.1) is estimated below 0.35 after 30 explanations in ~79%
    of runs, after 60 in ~94%, after 120 in ~98%. The pilot gives each learner ~40, so
    expect partial recovery. R6 should test lower noise (more signals per explanation) or a
    weaker prior._

## R6: Learner simulator + offline study (weeks 6–8)
- **Depends on:** R4, R5
- **Do:** `research/simulator/`: synthetic learners with ground-truth traits
  and mastery, a response model (BKT-generated answers plus a style-dependent
  success boost), and a driver that runs the **real** services in-process with
  the fake explainer. Report for H3 (`EVALUATION_PLAN.md`): trait recovery
  MAE vs number of explanations, regret, exploration share, and a comparison
  of the three arms. Output `research/reports/simulation.md` with plots.
- **Acceptance:**
  - [x] Reproducible (seeded); one command regenerates the report
  - [x] Constants in `MODEL_SPEC.md` re-tuned from the results and the
        changes documented
- [x] **R6 done**: `research/reports/simulation.md` (regenerate: see `research/README.md`)
  - _Findings (40 paired learners per arm, 60 explanations; well-specified world):_
    1. _With a self-report gap (SD 0.2), the closed loop cuts style-trait error by 36%
       (0.158 → 0.102) and keeps improving (0.079 after 150). With accurate self-report there
       is little to learn (0.089 → 0.081). The loop's value depends on how wrong self-report
       is, so **the pilot should measure that gap**._
    2. _It does not invent preferences: with no true preference it claims one in 18% of
       estimates, vs 47% for questionnaire-only (it corrects questionnaire noise)._
    3. _Short horizons cost: over 60 explanations the closed loop beats generic on learning
       gain (+0.027, CI +0.006 to +0.047) but trails static (−0.016, CI −0.029 to −0.003),
       because Thompson sampling explores a lot. Regret only catches up with static after
       ~100 explanations. **Decision for Ronit:** keep full Thompson sampling (best for
       identifying traits, the research claim) or exploit more (better short-term
       learning). See MODEL_SPEC §2.2 "Checked in R6"._
    4. _The behavioural-trait EWMA made persistence/self-efficacy worse (0.160 → 0.223), so
       it is now off by default until calibrated (MODEL_SPEC §2.3)._
    5. _Constants kept (ε = 0.1, questionnaire variance 0.04); the sweep did not justify a
       change._

## R7: Hardening (weeks 7–8)
- **Depends on:** R5
- **Do:** load test `get_state`/`apply_*` (100 simulated concurrent users),
  fix N+1 queries, add a demo seed (`python -m app.graph.demo_seed`: 3 demo
  learners with interesting states), and go through your own code for edge
  cases (a new user, a concept with no items, deleted users).
- **Acceptance:**
  - [ ] p95 within the budgets in `ARCHITECTURE.md` under load
- [ ] **R7 done**

## R8: Pilot analysis + resonance/drift backtest (weeks 9–12)
- **Depends on:** pilot data; S2 pre-registration committed
- **Do:**
  - `research/analysis/`: H1 (AUC/log-loss with and without feedback
    features, CV split by learner), H2 (mixed-effects logistic regression),
    H4 (normalised gain with 95% CI), α reliability.
  - `research/backtest/`: resonance (`MODEL_SPEC §6`) and CUSUM drift lead
    time vs a logistic baseline.
  - `research/reports/results.md`
- **Acceptance:**
  - [ ] Every pre-registered hypothesis is reported, including nulls
  - [ ] Every number in the report is regenerated by one command
- [ ] **R8 done**

---

## Asks for Mit
_(add items here when you need something from Mit's side)_
- **Questionnaire API (M1):** `GET /onboarding/questionnaire` should return
  `list[QuestionnaireItemPublic]` from `app/psychometrics/questionnaire.py`
  (id + text only; never send trait, reverse flag or source). Load the items with
  `LearnerModel.questionnaire_items()`. If you'd rather have this model in
  `contracts/`, open a `contract` PR and I'll approve it.
- **Wiring (M1):** `LearnerModel(session, graph)` needs a `GraphSnapshot`. Build it once at
  startup with `GraphSnapshot.from_db(session)` (pass `include_drafts=True` in dev until items
  are approved) and reuse it. `apply_*` methods flush but don't commit: commit in the request.
- **Users table:** R0 added `users.is_admin` (bool, default false) for the `/admin/*` guard.
- **Attempt then feedback order (M1/M2):** for a micro-check, call
  `apply_attempt(...)` first and `summarize` + `apply_explanation_feedback(...)` after it. The
  feedback update reads the attempt's pre-answer mastery to compute `p̂`. Both calls are
  idempotent, so retries are safe.
- **Style (M1):** call `planner.choose_style(state, rec.target_concept_id)` and pass the
  result into `ExplanationRequest` unchanged. `include_diagram` and `tone` are already decided.

## Notes / decisions log
_(date: decision, and why)_
