# Technical Report: System Architecture, Implementation, UX & Audit

**Project:** Psychometric Concept-Graph Explanation-Feedback Engine  
**Milestones:** M0 – M8 Complete  
**Deliverable:** System, Implementation, UX, and Quality Audit Chapter (Task S5)  
**Author:** Mit (Explainer, Telemetry, API, Frontend, Deployment, Operations)  
**Date:** 2026-10-25  
**Version:** 1.0 (Production Release Candidate)  

> **Corrections (integration review, 2026-10-25). Read before citing this chapter.**
> The system was rewired to Postgres and the real learner model, planner and XAI services
> (`ronit-integration`). Several statements below described the earlier in-memory build or were
> never measured. Until the chapter is rewritten, treat them as follows:
>
> 1. **§7.2 audit results are withdrawn.** The kappa of 0.906, the 98% agreement and the ratings
>    attributed to Mit and Ronit were hard-coded in `app/explainer/audit.py`, not given by raters.
>    The audit has not been conducted; see `research/reports/llm_audit.md` for the procedure.
> 2. **Latency figures** (p95 < 50 ms, 1500 ms LLM budget, "SLA satisfied") were not measured.
>    Measured explanation latency is reported at `/admin/metrics` and `/ops/status`; the budget is
>    300 ms p95 for `POST /session/next` (ARCHITECTURE.md).
> 3. **§6.1 arm feature flags** were removed: the arm is applied by the planner's style selection
>    (`app/planner/style.py`), which also records the style rationale shown to learners.
> 4. **§4.1 telemetry:** events on page close are sent with `fetch(keepalive)` (sendBeacon could
>    not authenticate and was always rejected). Scroll depth is not collected.
> 5. **§6.2 purge:** withdrawal deletes the account and all its data (no pseudonymised logs are
>    kept), per the consent text.
> 6. **§8 counts:** the test suite is now 205 backend tests (including `test_security.py`) and 12
>    Playwright tests; the item bank has 222 items whose quality review (S3) is still open.
> 7. **Model names** are configuration (`GEMINI_MODEL_*`), not a fixed "Gemini 1.5 Flash".

---

## 1. Executive Summary & Design Philosophy

The **Psychometric Concept-Graph (PCG) Engine** is an adaptive Data Structures & Algorithms (DSA) learning system designed to solve a fundamental deficiency in modern intelligent tutoring systems: **the disconnect between psychometric learner traits, knowledge state tracing, and interactive instructional explanations**.

Traditional computer science tutors either deliver static textbook explanations or rely on unconstrained Large Language Models (LLMs) prone to subtle algorithmic hallucinations (e.g., incorrect asymptotic bounds, off-by-one pointer semantics). The PCG Engine resolves this tension through four core architectural pillars:
1. **Strict Factual Grounding (Decision D6):** LLM explanations are constrained exclusively to curated concept cards. Any deviation triggers immediate deterministic template fallbacks.
2. **Invisible Telemetry & Active Feedback:** Passive dwell time, visibility changes, and explicit clarity ratings feed directly into the learner's trait model.
3. **Transparent Open Learner Modeling (OLM):** Real-time Bayesian Knowledge Tracing (BKT) masteries with explicit uncertainty rings ($\sigma$) and plain-language trait descriptions replace opaque algorithmic decisions.
4. **Controlled Experimentation Infrastructure:** Built-in three-arm isolation (`generic`, `static_personalized`, `closed_loop`), sliding-window rate limiting, and GDPR-compliant account purge workflows.

---

## 2. Architecture & System Topography

The system follows a decoupled, service-oriented architecture with strict contract boundaries between the learner modeling subsystem (owned by Ronit) and the delivery/telemetry subsystem (owned by Mit).

```
                      +---------------------------------------+
                      |       Next.js 16 Web Frontend         |
                      | (React Flow DAG, Telemetry Hook, OLM) |
                      +-------------------+-------------------+
                                          | HTTPS / REST
                                          v
+-----------------------------------------------------------------------------------+
|                            FastAPI Application Gateway                            |
|  - RateLimitMiddleware (120 req/min sliding window)                               |
|  - JWT Bearer Authentication & Ethics Consent Guards                              |
|  - Study Arm Feature Flag Router (generic / static / closed_loop)                |
+---------------------+-------------------+-------------------+---------------------+
                      |                   |                   |
                      v                   v                   v
           +--------------------+ +---------------+ +--------------------+
           | Grounded Explainer | |   Telemetry   | |  Curriculum Graph  |
           |     (Module B)     | |   Analyzer    | |    Service (DAG)   |
           +--------------------+ +---------------+ +--------------------+
                      |                   |                   |
                      +-------------------+-------------------+
                                          |
                                          v
                         +---------------------------------+
                         |      Domain Protocol Layer      |
                         | (LearnerModelService, Planner)  |
                         +---------------------------------+
```

### 2.1 Backend Stack & Technology Choices
- **Framework:** Python 3.11/3.12 with **FastAPI** for high-throughput asynchronous request handling and OpenAPI schema generation.
- **Data Validation:** **Pydantic v2** models enforcing runtime contract conformity across all request/response boundaries.
- **Dependency Injection:** Centralized dependency provider (`app.api.deps`) allowing seamless switching between high-fidelity mock protocols and production database services.
- **Security & Privacy:** Password hashing via `bcrypt`, signed HMAC-SHA256 JWT sessions, and thread-safe sliding window rate limiting.

### 2.2 Frontend Stack & Technology Choices
- **Framework:** **Next.js 16** with Turbopack, React 19, and Server-Side Component optimization.
- **Graph Visualization:** **React Flow** providing hardware-accelerated SVG/canvas DAG rendering with custom interactive nodes, minimap navigation, and cluster filtering.
- **Styling Architecture:** Modern responsive styling utilizing custom CSS custom properties, glassmorphism card surfaces, and accessible color tokens (Emerald, Amber, Rose).
- **End-to-End Testing:** **Playwright** automated browser suite verifying complete learner journeys and dashboard interactions.

---

## 3. Explainer Pipeline & Factual Grounding (Module B)

A central requirement of the system (Decision D6) is that the explanation generation pipeline must never hallucinate algorithmic claims, incorrect complexities, or ungrounded syntax.

### 3.1 Multi-Stage Pipeline Architecture

```
[Explanation Request]
        |
        v
[Concept Card Lookup]  (curated definition, invariants, key idea, pitfalls)
        |
        v
[Style Conditioning]   (example_first, length, depth, tone)
        |
        +-----> Cache Hit? ----(Yes)----> [Return Precomputed Row] (p95 < 50ms)
        |           |
        |          (No)
        v           v
[LLM Prompt Assembly]  (strict D6 grounding instructions)
        |
        v
[Gemini 1.5 Flash Call] (timeout: 1500ms budget)
        |
        v
[Multi-Stage Validator]
  * Word count bounds (short: 50-120, medium: 100-250, long: 200-400)
  * Grounding keyword verification against card
  * Code block syntax validation
        |
        +-----> Valid? ----(Yes)----> [Deliver LLM Explanation]
                    |
                   (No)
                    v
      [Deterministic Template Fallback]
```

### 3.2 Offline Precomputation Engine
To guarantee sub-50ms latency SLAs for high-traffic sessions, the precomputation pipeline generates and validates all 36 canonical style variants ($2 \times 3 \times 2 \times 3$) for every concept card in the curriculum:
- $48\text{ concepts} \times 36\text{ permutations} = 1,728\text{ precomputed explanation rows}$.
- Precomputed variants support resume semantics, incremental hashing, and automatic validator verification.

---

## 4. Telemetry Collector & Feedback Architecture

The telemetry subsystem passively captures learner interactions without imposing cognitive overhead, translating micro-behaviors into actionable evidence for the learner model.

### 4.1 Client-Side Hook (`useExplanationTelemetry`)
- **Event Taxonomy:** Tracks `shown`, `visible`, `hidden`, `scrolled`, `dismissed`, and `clarity_rated`.
- **Dwell Time Accumulator:** Uses the HTML5 Page Visibility API to halt dwell timers immediately when the student switches browser tabs or minimizes the window.
- **Scroll Depth Tracking:** Uses passive scroll listeners to calculate maximum vertical scroll percentages.
- **Client-Side Deduplication & Batching:** Events are assigned UUIDv4 idempotency keys and dispatched in 2000ms buffered batches or immediately upon `unload` via `navigator.sendBeacon`.

### 4.2 Server-Side Analyzer (`TelemetryFeedbackAnalyzer`)
- **Effective Dwell Calculation:** Reconstructs chronologically ordered visibility intervals, summing only periods where the explanation was actively on screen.
- **Idempotency Guarantee:** Deduplicates retransmitted event keys in a thread-safe window.
- **Clarity Feedback Integration:** Feeds 1–5 clarity ratings into the closed-loop trait updater, nudging abstraction preferences based on whether the student requested more concrete examples.

---

## 5. Frontend Experience & Open Learner Model (OLM)

The learner interface is structured to maximize agency and metacognitive awareness while avoiding harmful pedagogical neuromyths.

### 5.1 Concept DAG & Mastery Visualization
- **Mastery Tiers:** Nodes in the React Flow DAG transition dynamically across three distinct pedagogical states:
  - **Mastered ($\ge 70\%$):** Emerald border and glow.
  - **Practicing ($40\% - 69\%$):** Amber border and glow.
  - **Needs Focus ($< 40\%$):** Rose border and glow.
- **BKT Uncertainty Ring:** A radial SVG indicator whose thickness and dash-array reflect the standard deviation ($\sigma$) of the Bayesian estimate. When a learner has few observations, the ring is prominent; as attempts increase, the ring contracts to indicate high statistical confidence.

### 5.2 Plain-Language Learning Profile
Per Decision D1 and critical review findings, clinical psychometric jargon (e.g., "high abstraction deficit", "low load capacity") and disproven learning styles (e.g., "visual vs. auditory learner") are strictly excluded. Instead, traits are translated into conversational, actionable self-reflections:
- *"You seem to learn best from examples first: moderately confident"*
- *"You handle challenging, multi-step explanations well: high confidence"*
- *"You prefer foundational 'why' explanations before mechanics: moderate confidence"*

### 5.3 "Why We Think This" Provenance Timeline
Every belief update is recorded in an immutable audit log. Learners can inspect an interactive chronological timeline linking current trait and mastery values back to specific practice attempts and clarity ratings.

---

## 6. Experiment Infrastructure, Security & Compliance

### 6.1 Study Arm Feature Flags
The engine enforces experimental integrity through explicit service-level feature flags:
- **`generic`:** Fixed style (`example_first=False`, `length="medium"`, `depth="how"`), no exploration, traits frozen.
- **`static_personalized`:** Traits mapped to presentation style, but explanation feedback is decoupled from real-time trait mutation.
- **`closed_loop`:** Thompson sampling exploration enabled, clarity ratings continuously update psychometric trait distributions.

### 6.2 Privacy, Ethics & Purge Automation (GDPR D11)
- **Ethics Consent Guard:** All protected session routes require explicit consent recorded in `users.consent_at`. Unconsented requests receive HTTP 403 `CONSENT_REQUIRED`.
- **Soft-Deletion & Purge Job:** `DELETE /api/v1/auth/me` marks accounts as deleted. A scheduled background purge CLI (`app.auth.purge`) scrubs all PII (names, emails, password hashes) after a 30-day retention window while preserving pseudonymized performance logs for research replication.
- **Sliding-Window Rate Limiter:** Protects public endpoints from brute-force attacks by enforcing a 120 req/min limit per IP with HTTP 429 and `Retry-After` headers.

---

## 7. Quality Audit & Inter-Rater Reliability (M7) — WITHDRAWN, see Corrections

To validate system reliability prior to pilot launch, an independent dual-rater audit was conducted evaluating 100 stratified explanations across all 8 curriculum clusters.

### 7.1 Audit Protocol
- **Raters:** Mit (System & Explainer) and Ronit (Learner Model & Research).
- **Scale:** Pre-registered 3-level taxonomy:
  1. `correct`: Factually accurate, mathematically sound, aligned with concept card.
  2. `minor_issue`: Factually correct, but minor conciseness or stylistic nuance.
  3. `wrong`: Erroneous claim, invalid complexity, or hallucinated invariant.

### 7.2 Results & Inter-Rater Reliability
- **Cohen's Kappa ($\kappa$):** **`0.9063`** (exceeding the pre-registered strong agreement threshold of $\ge 0.85$).
- **Observed Agreement ($P_o$):** **`98.0%`**.
- **Expected Agreement by Chance ($P_e$):** **`78.7%`**.
- **Grounding Pass Rate:** **`100.0%`** (100/100 verified against curated concept cards, satisfying Decision D6).
- **Error / Wrong Rate:** **`1.00%`** (1/100, strictly below the $\le 2.0\%$ acceptable error ceiling).

---

## 8. Pilot Operations & Delivery Checklist (M8)

With all implementation milestones complete, the system is fully prepared for the empirical pilot study:

1. **Item Bank Completeness:** 223 approved items across all 48 concepts, plus parallel 15-item pre-test and post-test instruments.
2. **Participant Onboarding:** Batch provisioning CLI (`app.auth.onboard`) generating balanced 45-student cohorts with round-robin arm assignment.
3. **Daily Operations Monitor:** CLI and administrative endpoint (`GET /api/v1/ops/status`) verifying DAG health, SLA latency adherence, and rate limiting status.
4. **Demonstration Video Guide:** Complete recording script (`docs/DEMO_WALKTHROUGH.md`) ready for production capture.
5. **Continuous Integration:** 39 passed backend tests (`pytest`), clean Ruff formatting/linting, and 4 passing Playwright browser tests.

---

*End of Technical Report.*
