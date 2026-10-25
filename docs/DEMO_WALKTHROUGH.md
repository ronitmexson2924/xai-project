# Demo Walkthrough

A 5-minute tour of the running system for a recording or a review. Everything shown is produced by
the real services on Postgres; nothing on screen is mocked.

## Setup (once)

```bash
cd backend
alembic upgrade head && python -m app.graph.seed ../content
python -m app.graph.demo_seed --password 'Demo-pass-1'     # development databases only
python -m app.auth.onboard admin --email admin@example.com
INCLUDE_DRAFT_ITEMS=true uvicorn app.main:app &   # the item bank is still in review
cd ../frontend && npm run dev                               # http://localhost:3000
```

Demo learners (all consented; log in with the password above):

| Account | Arm | State built by the real learner model |
|---|---|---|
| `asha@demo.example.com` | closed loop | New: questionnaire says example-first and short explanations; 2 answers |
| `ben@demo.example.com` | static | Basics mastered; a flagged misconception on recursion base cases and a prerequisite gap |
| `chen@demo.example.com` | closed loop | Advanced; 24 explanation ratings have taught the system rule-first, long, "why" explanations |

The arm is not shown anywhere in the learner UI (participants are blinded); the table is for the
presenter.

## Scenes

1. **A new learner (1 min).** The landing page (`/`) → **Get started** → sign up (`/signup`) →
   onboarding (`/onboarding`): the consent step explains the data collected and that the version of
   the app is assigned at random (nothing is pre-ticked) → the 20-item questionnaire, one statement
   per screen, answerable with keys 1–5 (no trait names shown) → "You're all set" → the dashboard,
   whose next-step card offers the pre-test (submitted once, no score) → `/session`. Logging in
   again goes straight to the dashboard.
2. **Placement (30 s).** The first questions are placement questions: the question comes first,
   and the explanation only after the answer. Open **Why this?**: "This is placement question 1 of
   8 …".
3. **Ben: fixing a misconception (1 min).** Log in as Ben → `/session`. The explanation comes first
   and its question is the micro-check. Open **Why this?**: the rule that fired with the actual
   numbers, the alternative the planner passed over, and **What would change it** (verified
   counterfactuals: each was re-run through the planner). Answer → **What this changed** lists the
   mastery change in plain words.
4. **Chen: adaptation you can inspect (1 min).** Log in as Chen → `/session` → **Why this?** →
   *Why the explanation looks like this*: the style source, the posterior probability that this
   style suits Chen best, and how sure the system is. Rate the explanation with the 1-tap prompt.
5. **Open learner model (1 min).** `/dashboard`: the concept map grouped by topic and coloured by
   estimated mastery; select a concept for a drawer with *why we think this*, how many answers the
   estimate rests on, and the concept's key idea; the trait panel shows each estimate's own
   explanation and evidence; recent activity lists every update in plain words. `/account` shows
   the learner's details and lets them withdraw.
6. **Study admin (30 s).** Log in as the admin → `/admin`: arm balance, measured explanation
   latency against the 300 ms budget, clarity ratings, and pseudonymised CSV exports.

Every screen follows the system's light or dark setting, works at phone width (tabs move to a
bottom bar) and honours "reduce motion".

## Things worth showing a sceptical reviewer

- `backend/tests/test_security.py`: forged tokens, other learners' ids, replays, injection.
- `frontend/tests/abuse.spec.ts`: the same in a real browser (XSS in names, double submits, token
  tampering, offline API).
- `frontend/tests/experience.spec.ts`: keyboard-only onboarding, dark mode, phone width, and basic
  accessibility checks (named controls, labelled inputs, one heading per page) on every screen.
- `research/reports/llm_audit.md`: the explanation audit is still to be done by two human raters;
  no figures are claimed before it is.
