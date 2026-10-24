# Data Model (PostgreSQL)

Ronit writes the initial Alembic migration for **all** tables below in task
R0. The owner column says who may change a table afterwards. Column types are
PostgreSQL. `jsonb` payloads must match the Pydantic models in
`backend/app/contracts/`.

## Identity & experiment (owner: Mit)

| Table | Columns | Notes |
|---|---|---|
| `users` | `id uuid pk`, `email text unique`, `password_hash text`, `display_name text`, `created_at timestamptz`, `consent_at timestamptz null`, `deleted_at timestamptz null` | Learning endpoints require consent. Deletion is soft, then purged. |
| `experiment_assignments` | `user_id uuid pk fk users`, `arm text check in ('generic','static_personalized','closed_loop')`, `assigned_at timestamptz` | Balanced randomisation at signup. |

## Concept graph & content (owner: Ronit, except `items` which is Mit)

| Table | Columns | Notes |
|---|---|---|
| `concepts` | `id text pk` (slug, e.g. `recursion-base-case`), `name`, `cluster`, `description`, `difficulty smallint 1..5`, `card jsonb` | `card` = concept card (definition, key_idea, worked_example, pitfall, diagram?). Loaded from `content/concepts.yaml`. |
| `concept_edges` | `src text fk`, `dst text fk`, `weight real default 0.8`, pk `(src,dst)` | `src` is a prerequisite of `dst`. The graph must be a DAG (enforced by a test). |
| `misconceptions` | `id text pk`, `concept_id text fk`, `description text`, `remediation_hint text` | At least one per concept. |
| `items` | `id text pk`, `concept_id fk`, `kind text ('mcq','short','code_trace')`, `stem text`, `options jsonb`, `answer text`, `difficulty smallint`, `distractor_misconceptions jsonb` (option → misconception id), `is_microcheck bool`, `review_status text ('draft','approved','rejected')` | Only `approved` items are served. |
| `questionnaire_items` | `id text pk`, `trait text`, `text text`, `reverse_scored bool`, `source text` | `source` = citation of the original scale. |

## Learner state (owner: Ronit)

| Table | Columns | Notes |
|---|---|---|
| `learner_concept_state` | `user_id`, `concept_id`, `p_mastery real`, `n_attempts int`, `misconception_ids text[]`, `misconception_suspicion real default 0`, `updated_at`, pk `(user_id, concept_id)` | Created lazily. A missing row means the prior. |
| `learner_traits` | `user_id pk`, `traits jsonb` (`TraitName` → `{mean, variance, n_observations}`), `bandit jsonb` (posterior parameters), `version int`, `updated_at` | `version` gives optimistic concurrency. |
| `learner_affect` | `user_id pk`, `engagement real`, `frustration real`, `fatigue real`, `updated_at` | Rolling estimates. |
| `questionnaire_responses` | `user_id`, `item_id`, `value smallint 1..5`, `created_at`, pk `(user_id,item_id)` | |
| `state_updates` | `id bigserial pk`, `user_id`, `source text ('attempt','explanation_feedback','questionnaire')`, `source_id text`, `delta jsonb` (`StateDelta`), `created_at` | Audit log. Used for "why we think this" and for evaluation. A unique `(source, source_id)` makes updates idempotent. |

## Session activity (owner: Ronit for attempts and recommendations, Mit for explanations and events)

| Table | Columns | Notes |
|---|---|---|
| `recommendations` | `id uuid pk`, `user_id`, `kind text`, `target_concept_id`, `item_id null`, `reasons jsonb` (`list[ReasonEvidence]`), `policy_version text`, `created_at` | |
| `attempts` | `id uuid pk`, `user_id`, `item_id`, `recommendation_id null`, `explanation_id null`, `response text`, `correct bool`, `latency_ms int`, `hints_used int`, `confidence smallint null`, `created_at` | `explanation_id` is set when the item is a micro-check. |
| `explanation_variants` | `id uuid pk`, `concept_id`, `style_key text`, `body_markdown text`, `prompt_version text`, `model text`, `validation jsonb`, `review_status text ('auto_ok','approved','rejected')`, `created_at`, unique `(concept_id, style_key, prompt_version)` | Precomputed explanations (D6). |
| `explanations` | `id uuid pk`, `recommendation_id fk`, `user_id`, `concept_ids text[]`, `style jsonb` (`StyleParams`), `style_source text`, `body_markdown text`, `source text ('precomputed','llm','template')`, `variant_id null`, `followup_item_id null`, `prompt_version`, `model null`, `latency_ms int`, `created_at` | What was actually shown. |
| `explanation_events` | `id bigserial pk`, `idempotency_key uuid unique`, `explanation_id fk`, `user_id`, `type text`, `payload jsonb`, `client_ts timestamptz`, `server_ts timestamptz default now()` | Append-only. |
| `explanation_feedback` | `explanation_id pk`, `summary jsonb` (`ExplanationFeedbackSummary`), `applied_at timestamptz null` | Written by the telemetry analyzer, consumed once by the learner model. |

## Indexes worth creating from day 1

- `attempts (user_id, created_at desc)`
- `explanation_events (explanation_id)`
- `recommendations (user_id, created_at desc)`
- `state_updates (user_id, created_at desc)`
