# Critical Review: Is This Idea Good?

Written as a skeptical reviewer would write it: every claim gets a question.
The aim is to fix the weak points before a guide, a patent examiner or real
students find them.

---

## 1. Verdict

| Dimension | Score | One-line reason |
|---|---|---|
| Problem & research framing | **8/10** | The gap is real: adaptive learning and learner-facing XAI have grown up apart. The lit review supports it. |
| Novelty, as currently claimed | **6/10** | Narrower than the documents say. See §3: Open Learner Models and hint-usage modelling already exist. |
| Technical soundness of the current spec | **4/10** | The resonance formula is miscalibrated, drift is undefined, and "learning styles" is a weak construct. All fixable. |
| Feasibility for 2–3 students in ~12 weeks | **7/10** | Doable only with a hard scope: one domain, ~60 concepts, precomputed explanations. |
| Evaluability (can you *prove* it works?) | **5/10** | No evaluation design exists yet. A small pilot can't show learning gains. Needs the design in `EVALUATION_PLAN.md`. |
| **Overall, as a project today** | **6.5/10** | Strong idea, under-specified engine. |
| **Overall, if the fixes in this doc are applied** | **8–8.5/10** | Defensible novelty, a measurable claim and a working closed loop. |

**Bottom line:** the idea is good enough to build, but not in its current form.
The core idea is strong: *explanation interaction is a feedback signal that
updates the learner model, which then reshapes the next explanation.* The
surrounding claims (resonance score, cognitive drift, five-graph architecture,
visual/theory/practical learners) are where a reviewer will attack. Build the
core loop first, measure it honestly, and promote Phase-2 ideas only when the
data supports them.

---

## 2. Questioning every claim

### 2.1 "Resonance score R = P × C × B × T"
- **Problem: a product of four values in [0,1] collapses toward zero.** A
  learner scoring 0.80 on every component gets R = 0.41, which your table
  calls *"Potential struggle"*. At 0.70 everywhere, R = 0.24, which is *"High
  intervention required"*. To reach *"Strong alignment"* (≥ 0.80), every
  component has to be ≥ 0.946. The bands do not match the formula.
- **Problem: one missing component sets R to 0.** At cold start, T or B is
  unknown. If it defaults to 0, every new learner lands in *"Immediate
  remediation"*.
- **Fix:** use a weighted geometric mean, `R = P^wP · C^wC · B^wB · T^wT` with
  Σw = 1. It stays on the same scale as its inputs (all 0.8 → R = 0.8). Better
  still, treat P, C, B and T as *features* of a logistic model that predicts
  next-task failure, and calibrate the thresholds on logged data. The
  thresholds then come from evidence rather than assumption.

### 2.2 "Cognitive drift = |Expected − Observed|"
- **Question:** expected *what*, from *which model*? As written, the formula
  cannot be implemented.
- **Fix:** let Expected be the mastery model's predicted P(correct) for the
  next item and Observed be the actual result. Drift is a CUSUM over the
  residuals. This is concrete, testable and standard. See `MODEL_SPEC.md`.

### 2.3 "Visual learner / theory learner / practical learner"
- **This is the biggest credibility risk.** The "learning styles" *meshing
  hypothesis* (that matching instruction to a self-reported style improves
  learning) has repeatedly failed rigorous tests; see Pashler et al., 2008,
  *Psychological Science in the Public Interest*. Education reviewers know this
  literature well.
- **Fix:** use constructs with evidence behind them:
  - *Cognitive load* and *expertise reversal*: novices benefit from worked
    examples first, while experts are slowed by them. This gives
    `abstraction_preference` and `load_tolerance`.
  - *Need for cognition* and depth preference: "why" vs "how" explanations.
  - *Persistence* and *self-efficacy*: measured behaviourally and with short
    published scales.
  - Present "visual vs text" as a **preference you test**, not a trait you
    assume. The bandit in `MODEL_SPEC.md` does exactly that.

### 2.4 "Psychometric traits from short validated instruments"
- **Question:** which instruments? "Validated" has to name a scale and a
  citation, and check its licence terms. Short scales (3–4 items per trait)
  have low reliability, so expect Cronbach's α around 0.6–0.7.
- **Fix:** name the source scale for each item, report α on your pilot data,
  and store every trait as **mean + uncertainty**, never as a single number.
  The uncertainty is also what makes Novelty 4 (confidence signalling) real.

### 2.5 "Explanation interaction updates both the psychometric vector and the mastery graph"
- **Identifiability problem:** suppose a learner spends 90 seconds on an
  explanation and then gets the follow-up wrong. Is the concept unmastered, is
  the explanation too dense for them, or did they switch tabs? One signal
  can't update two models without a rule for assigning cause.
- **Fix (the key design decision of this project):**
  - Follow-up micro-check correctness updates **mastery**, as normal evidence.
  - The *contrast between explanation styles* updates **traits**. The system
    deliberately varies style (micro-randomised) and learns which style works
    for this learner. Formally this is a Bayesian linear contextual bandit, and
    its posterior over parameters *is* the trait vector.
  - Dwell time counts only while the card is visible (Page Visibility API).
- **Feedback-loop risk (filter bubble):** if the system decides someone
  prefers examples and only shows examples, it can never learn otherwise.
  Exploration (Thompson sampling with a floor) prevents this.

### 2.6 "No surveyed prior art closes this loop"
- **Prior art the documents leave out:**
  - **Open Learner Models** (Bull & Kay, and others): learner-facing displays
    and explanations of the learner model. This field is decades old.
  - **Help-seeking and hint-usage modelling** (Aleven et al.; ASSISTments-based
    knowledge-tracing work): learner interaction with help content has long
    been used as a modelling signal.
  - **Commercial products:** LLM tutors that explain answers (Khanmigo,
    Duolingo's "Explain my answer", and similar).
- **What still looks novel:** the explanation's *presentation parameters* are
  chosen from a probabilistic trait model, and the learner's response to *that
  specific presentation* is used to *update the trait model*. In other words,
  explanation style is treated as an experiment that identifies the learner's
  psychometric parameters, within a concept-graph learner model. That is a
  sharper, more defensible claim. Lead with it.

### 2.7 The patent
- The patent review cites `[web:49]`-style placeholders and patent numbers
  such as `US12561435B2`. **These have not been verified here.** Check every
  one on Google Patents, Espacenet or InPASS before showing the document to
  anyone.
- **India, Patents Act §3(k):** "a mathematical or business method or a
  computer programme per se or algorithms" are not patentable. Claims need a
  technical effect. Talk to the VIT IPR cell or a patent agent early.
- **Public disclosure:** check whether the repo, the slide deck, or a
  presentation already made the method public. Most jurisdictions,
  including India, offer little or no grace period. **Keep this repo private
  and file a provisional application before publishing** a paper or demo.

### 2.8 Inconsistencies in the existing documents
- The Phase-1 diagram uses `TaskService`, `TaskEventBus` and *Zod*, which is a
  TypeScript library. The patent document says FastAPI. **This repo starts
  fresh on FastAPI + Postgres + Next.js** (decision D2 in `PROJECT_BRIEF.md`).
  If you want to port SkillSpring's Phase-1 code instead, decide in week 1.
- The deck marks Phase 1 as "IMPLEMENTED", but this repo is empty. Be clear
  with your guide about which parts are new work.
- The deck credits "Naval" while the team here is Ronit and Mit. Make sure
  authorship and inventorship are agreed in writing.

---

## 3. How the app will perform in the real world

Assumed pilot: ~40 VIT students, 3 weeks, DSA, voluntary use plus some
incentive.

| Area | What will realistically happen | What to do about it |
|---|---|---|
| **Usage** | Voluntary ed-tech use usually drops sharply after week 1. Without an incentive, expect a large share of students to stop. | Attach it to a lab or course activity. Use short (10–15 min) sessions. |
| **Data volume** | Roughly 40 × 5 sessions × 15 items ≈ 3,000 attempts and ~1,500 explanation views. That is about 50 attempts per concept: enough for coarse global BKT parameters, not for per-learner fitting. | Fit BKT parameters globally. Use priors. Be honest about uncertainty. |
| **Trait updates** | With ~40 explanation interactions per learner, trait posteriors move only modestly from the questionnaire prior. | Report posterior shift and uncertainty. Use the simulator (`R6`) to show the loop converges with more data. |
| **Clarity ratings** | Rating fatigue: answer rates drop quickly after the first few prompts. | Make rating one tap. Ask on about 1 in 3 explanations. Never block on it. |
| **Dwell time** | Noisy: tab switches, phone notifications, people reading fast and skipping. | Count visible time only, cap outliers, and use it only as a weak signal. |
| **LLM latency & cost** | A live Pro-class call per explanation takes seconds. That is too slow for a learning flow, and costs grow with users. | **Precompute** explanation variants (concept × style bucket ≈ 720) offline, review them, and serve from the database in under 50 ms. Use live LLM calls only for rare cases, with a timeout and template fallback. |
| **Hallucination** | LLMs make subtle DSA errors, such as wrong complexities or off-by-one examples. | Ground every explanation in a curated *concept card*, validate the output, and audit 100 samples with two raters. |
| **Statistical power** | With ~20 students per arm, a between-group test detects only large effects (d ≈ 0.9). Learning-gain differences will probably be inconclusive. | Use **within-learner micro-randomisation** of explanation style: hundreds of observations per arm. Make the main claim *predictive* ("explanation-interaction features improve next-answer prediction"), which is testable with this sample size. |
| **What will likely work well** | Concept-graph remediation ("you're stuck on recursion because base-case mastery is 0.4"), a clear "why this?" for each recommendation, and the mastery dashboard. Students value these immediately. | Make them the centre of the demo. |
| **What may show only a small effect** | Trait-based style personalisation. Effect sizes in the literature are small. | Report it honestly. A small but real, well-measured effect is still a result. |
| **Privacy & ethics** | Psychometric data on students is sensitive personal data under India's DPDP Act 2023. A pilot with students needs consent and probably institutional ethics approval. | Use a consent screen, pseudonymous exports and a delete-my-data endpoint. Start the approval process in week 1. |

---

## 4. Changes adopted in this repo

1. Resonance uses a weighted geometric mean or a calibrated logistic model,
   and stays **offline research only** until a backtest shows lead time.
2. Drift is defined as a CUSUM over mastery-model residuals.
3. Learning styles are replaced by evidence-based constructs. Visual vs text
   is a tested preference.
4. Causal assignment: follow-up correctness updates mastery; style contrast
   updates traits; exploration is built in.
5. Explanations are precomputed, grounded in concept cards, validated, and
   have a template fallback.
6. Three experiment arms (`generic`, `static_personalized`, `closed_loop`)
   plus micro-randomisation.
7. Privacy, consent and ethics approval are tasks, not afterthoughts.
