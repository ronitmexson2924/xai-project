# Demo Walkthrough Guide & Recording Script

**Project:** Psychometric Concept-Graph Explanation-Feedback Engine  
**Task:** M8 (Pilot Ops & Delivery)  
**Author:** Mit (Explainer, Telemetry, API, Frontend, Deploy)  
**Target Duration:** 4–5 minutes  
**Format:** Screen recording with voiceover narration  

---

## 1. Overview & Demonstration Goals

This guide provides a structured, scene-by-scene script for recording the system demonstration video. The walkthrough showcases the complete closed-loop architecture:
1. **Consent & Onboarding:** Participant intake, GDPR D11 compliance, and psychometric trait estimation.
2. **Personalized Learning Experience:** Style-conditioned explanation delivery grounded in curated concept cards (Decision D6).
3. **Telemetry & Feedback Ingestion:** Invisible client-side behavioral capture (dwell, visibility, scroll depth) and clarity self-reporting.
4. **Open Learner Model (OLM):** Real-time BKT concept mastery visualization with uncertainty rings ($\sigma$), plain-language trait profiles, and provenance audit history ("Why we think this").
5. **Study Administration & Ops:** Experiment arm balancing, SLA latency monitoring, and pseudonymized research exports.

---

## 2. Demo Persona Profiles

Use the built-in Persona Switcher in the top navigation bar to demonstrate system behavior across three distinct learning profiles:

| Persona | Role | Arm | Initial Focus | Trait Characteristics |
|---|---|---|---|---|
| **Ada Lovelace** | Novice | `closed_loop` | `recursion-base-case` | Low abstraction preference (benefits from concrete examples first), moderate load tolerance, high persistence. |
| **Alan Turing** | Intermediate | `static_personalized` | `binary-search-bounds` | Balanced abstraction and depth preferences; steady progression across searching and trees. |
| **Grace Hopper** | Advanced | `generic` | `topological-sort` | High abstraction and load tolerance, prefers deep mathematical invariants and high depth. |

---

## 3. Scene-by-Scene Recording Script

### Scene 1: Introduction, Ethics Consent & Onboarding (0:00 – 0:45)

- **Visual:** Browser opens to `http://localhost:3000/login`.
- **Narration:**
  > "Welcome to the Psychometric Concept-Graph Explanation-Feedback Engine. In computer science education, one-size-fits-all explanations frequently fail because learners differ widely in cognitive load tolerance and abstraction preference. Our system bridges psychometrics and Bayesian Knowledge Tracing to personalize how concepts are explained, and uses learner interactions to continuously refine both trait estimates and mastery."
- **Action:**
  1. Click **"Need an account? Register"** or log in as a new student.
  2. Display the **Ethics Consent Screen** (`/consent`). Point out the clear disclosure regarding telemetry, pseudonymization, and the right to erasure (Decision D11).
  3. Click **"I Agree & Continue"**.
  4. Navigate to `/onboarding`. Complete the 5-item psychometric intake questionnaire (measuring abstraction preference, load tolerance, and depth preference).

---

### Scene 2: Persona Switching & The Learning Session (0:45 – 2:00)

- **Visual:** Session view (`/session`).
- **Narration:**
  > "Let's observe our Novice learner, Ada Lovelace, assigned to the closed-loop arm. Notice how the system personalizes her explanation for Recursion Base Cases."
- **Action:**
  1. Use the **Navbar Persona Switcher** and click **Novice (Ada Lovelace)**.
  2. Highlight the explanation body:
     - Notice that because Ada has a lower abstraction preference, the explanation places the **Worked Example First**, followed by the key invariant.
     - Note the grounding badge confirming facts are strictly derived from curated concept cards (D6).
  3. Scroll through the explanation to demonstrate client-side telemetry capture:
     - Dwell time accumulator tracking active reading.
     - Scroll depth triggers.
  4. Click the **"Rate Explanation Clarity"** button. Select **"Needs More Examples" (Rating 2)**.
  5. Explain that this feedback immediately logs a state delta nudging her abstraction preference mean.

---

### Scene 3: Practice & Misconception Diagnosis (2:00 – 2:45)

- **Visual:** Micro-check item card below the explanation.
- **Narration:**
  > "Following each explanation, learners engage with an approved formative assessment. Every distractor in our 223-item bank is explicitly mapped to common DSA misconceptions."
- **Action:**
  1. Select a distractor representing the `recursion-never-halts` misconception.
  2. Click **"Submit Answer"**.
  3. Highlight the instant feedback diagnosing the specific conceptual invariant that was violated, updating the learner's Bayesian Knowledge Tracing model.

---

### Scene 4: Open Learner Model Dashboard (2:45 – 3:45)

- **Visual:** Navigate to `/dashboard` (Open Learner Model).
- **Narration:**
  > "A core tenet of our design is transparency. The Open Learner Model allows students to inspect what the system believes about their mastery and traits without clinical jargon."
- **Action:**
  1. **Concept Knowledge Graph:**
     - Zoom in and pan across the 48-concept DAG.
     - Show color coding: Emerald ($\ge 70\%$ mastery), Amber ($40–69\%$), and Rose ($< 40\%$).
     - Point out the **BKT Uncertainty Ring** ($\sigma$), which shrinks as more observations accumulate.
     - Click on node `recursion-base-case` to open the Concept Detail Modal displaying definition, invariants, and detected misconceptions.
  2. **Plain-Language Learning Profile:**
     - Point out trait cards: *"You seem to learn best from examples first: moderately confident"*.
     - Contrast with the clinical terms (avoiding 'visual learner' neuromyths per critical review).
  3. **"Why We Think This" Provenance Timeline:**
     - Scroll through the chronological audit log showing the exact attempt and clarity rating events that caused recent belief updates.

---

### Scene 5: Study Operations & Administrative Analytics (3:45 – 4:30)

- **Visual:** Navigate to `/admin` (Study Analytics & Ops).
- **Narration:**
  > "Finally, let's look at the Administrative and Pilot Operations console used during our empirical study."
- **Action:**
  1. Review the **Study Arm Distribution** card showing balanced allocation across `generic`, `static_personalized`, and `closed_loop`.
  2. Show the **SLA Latency Budgets** (p50: 28.5ms, p95: 45.0ms, well within our 200ms target).
  3. Review the **Explanation Source Mix** (template vs precomputed vs real-time grounded LLM).
  4. Click **"Download Users CSV"**, **"Download Attempts CSV"**, and **"Download Assignments CSV"** to demonstrate automated, pseudonymized research exports ready for statistical analysis.

---

### Scene 6: Conclusion (4:30 – 4:45)

- **Visual:** Back to knowledge graph view or split screen of UI and architecture.
- **Narration:**
  > "The PCG Engine demonstrates how psychometric trait modeling, grounded LLM generation, and interactive telemetry can come together in an end-to-end, scientifically auditable DSA learning environment. Thank you."

---

## 4. Production Checklist

- [x] Backend running on `http://localhost:8000` with clean demo learner seeding.
- [x] Frontend running on `http://localhost:3000`.
- [x] Browser window set to 1920x1080 resolution at 100% zoom.
- [x] Audio input configured with noise cancellation.
- [x] Clear browser cache and storage before initial recording.
