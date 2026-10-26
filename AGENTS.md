# AGENTS.md: Instructions for AI coding agents

You are helping build the **Psychometric Concept-Graph Explanation-Feedback
Engine**: an adaptive DSA learning app whose explanations are shaped by a
learner's psychometric traits, and where the learner's interaction with each
explanation feeds back into their trait and concept-mastery model.

Two people build it, each with their own agent:
- **Ronit:** learner model, planner, content, research
- **Mit:** explainer, telemetry, API, frontend, deploy

## Step 1: Work out who you are working for

1. Run `git branch --show-current`.
   - `ronit` or `ronit-*` → you work for **Ronit**. Your task file is
     `tasks/ronit.md`.
   - `mit` or `mit-*` → you work for **Mit**. Your task file is
     `tasks/mit.md`.
   - Anything else (`dev`, `main`, `contract/*`, a `claude/*` branch) → **ask the user who
     they are** before changing code, and switch to their branch
     (`git checkout <name>`; create it from `origin/dev` if it doesn't
     exist).
2. Never commit to `dev` or `main` directly.

## Step 2: Load context (read in this order)

1. `docs/PROJECT_BRIEF.md`: what we're building and decisions D1–D11
2. Your task file: `tasks/ronit.md` or `tasks/mit.md`
3. `docs/ARCHITECTURE.md`: modules, the loop, **ownership table**
4. `backend/app/contracts/`: the typed interfaces between the two halves
5. As your task needs them: `docs/DATA_MODEL.md`, `docs/API_CONTRACT.md`,
   `docs/MODEL_SPEC.md`, `docs/EVALUATION_PLAN.md`
6. `docs/CRITICAL_REVIEW.md`: why the design looks the way it does. Read it
   before proposing a design change.

## Step 3: Pick and do a task

- The next task is the **first unchecked task in the task file whose
  "Depends on" items are done.** A dependency on the other person counts as
  done if its checkbox is ticked in their task file on `origin/dev`. If it
  isn't, use the fakes in `backend/app/contracts/fakes.py` and carry on.
- **Before coding:** summarise the task, list the files you'll touch, and
  confirm they are all in your owner's directories. If the task is large,
  show the plan and wait for approval.
- **While coding:**
  - follow the acceptance checks literally;
  - write tests alongside the code;
  - keep to the existing style (typed Python 3.12, Pydantic v2,
    SQLAlchemy 2.0 style, ruff defaults; TypeScript strict in `frontend/`).
- **After coding:**
  - run the checks below;
  - tick the task's boxes in the task file;
  - commit with `<TaskID>: <imperative summary>`;
  - push to the owner's branch.
- **Opening a PR:**
  - target `dev`;
  - title `[<TaskID>] <summary>`;
  - fill in `.github/pull_request_template.md`.

## Hard rules

- **Ownership:** only edit files your person owns (see `ARCHITECTURE.md`).
  Never change `backend/app/contracts/` inside a feature PR. Propose a
  separate PR labelled `contract` and tell your user that both people must
  approve it.
- **Model spec:** if you change any learner-model math, update
  `docs/MODEL_SPEC.md` in the same PR.
- **Secrets:** no secrets in code or commits. Read config from environment
  variables via `app/config.py`. Never hard-code LLM model names; they come
  from `.env`.
- **Grounding:** the explainer may only state facts that appear in the
  concept card it was given (decision D6).
- **No learning styles:** don't add "visual/auditory learner"-style traits.
  See `CRITICAL_REVIEW.md` §2.3.
- **Tests:** don't skip or delete tests to make CI pass.

## Checks to run before every push

```bash
# backend
cd backend
pip install -e ".[dev]"     # first time
ruff check . && ruff format --check .
pytest -q

# frontend (once it exists)
cd frontend && npm ci && npm run lint && npm run build
```

Local services: `docker compose up -d db` (Postgres on 5432). Copy
`.env.example` to `.env` first.

## Keeping in sync

Before starting work each day and before every PR:

```bash
git fetch origin && git merge origin/dev
```

Resolve any conflicts and re-run the checks. Details are in
`docs/GIT_WORKFLOW.md`.

## Things the human can ask you (and what you should do)

| They say | You do |
|---|---|
| "What's my next task?" | Steps 1–3: name the task, list its dependencies and their status, list the files, give a plan. Don't code yet. |
| "Do my next task" / "Do R2" | Plan → implement → test → tick boxes → commit → push to their branch. |
| "Status report" | For each task in their file: done / in progress / blocked (and on what). Also check the other person's file for anything that blocks them. |
| "Sync with dev" | Fetch, merge `origin/dev`, resolve conflicts, run checks, push. |
| "Open a PR" | Run the checks, then open a PR to `dev` using the template, with the task ID in the title. |
| "Prepare a release" | Only if both people have agreed: open a PR `dev → main` listing the tasks included and the checks run. |
