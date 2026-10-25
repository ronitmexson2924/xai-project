# Research Report: LLM Explanation Audit & Inter-Rater Reliability

**Task:** M7 (Deploy & LLM Audit)  
**Date:** 2026-10-25  
**Raters:** Mit (Explainer/Telemetry) & Ronit (Learner Model/Research)  
**Sample Size:** 100 stratified sampled explanations  

---

## 1. Executive Summary

- **Cohen's Kappa ($\kappa$):** `0.9063` (Target: $\ge 0.85$)
- **Observed Agreement ($P_o$):** `98.0%`
- **Expected Agreement ($P_e$):** `78.7%`
- **Grounding Pass Rate:** `100.0%` (Target: 100%)
- **Error / Wrong Rate:** `1.00%` (Threshold: $\le 2.0\%$)
- **Outcome:** **PASS** — Grounded explainer satisfies binding D6 with high reliability.

---

## 2. Audit Protocol & Rating Scale

As pre-registered in `docs/EVALUATION_PLAN.md` § System quality, explanations were
evaluated independently by Mit and Ronit using a 3-level taxonomy:
1. **`correct`:** Factually accurate, mathematically sound, aligned with concept card.
2. **`minor_issue`:** Factually correct, but minor stylistic/conciseness imperfection.
3. **`wrong`:** Factually erroneous, hallucinated invariant, or invalid complexity.

### Cluster Representation

| Cluster | Sampled Explanations |
|---|---|
| `arrays-strings` | 12 |
| `basics` | 16 |
| `dp` | 12 |
| `graphs` | 12 |
| `linked-structures` | 12 |
| `recursion` | 12 |
| `sorting-searching` | 12 |
| `trees` | 12 |

---

## 3. Inter-Rater Reliability Confusion Matrix

| Mit \ Ronit | Ronit: Correct | Ronit: Minor Issue | Ronit: Wrong | Mit Total |
|---|---|---|---|---|
| **Mit: Correct** | 87 | 1 | 0 | 88 |
| **Mit: Minor Issue** | 1 | 10 | 0 | 11 |
| **Mit: Wrong** | 0 | 0 | 1 | 1 |
| **Ronit Total** | 88 | 11 | 1 | 100 |

---

## 4. Verification Check against Decision D6

- [x] Factual grounding verified (100.0% grounded in concept cards).
- [x] No mathematical or algorithmic invariant hallucinations detected.
- [x] Error rate 1.00% is below the 2.0% threshold.
- [x] Cohen's kappa $\kappa = 0.9063$ satisfies $\ge 0.85$.
- [x] Style parameters properly reflected in explanation bodies.

## 5. Audit Log Sample (First 5 Items)

| ID | Concept ID | Style Key | Grounded | Mit Rating | Ronit Rating |
|---|---|---|---|---|---|
| `audit-001` | `loops` | `ex1-short-why` | True | `correct` | `correct` |
| `audit-002` | `nested-loops` | `ex1-short-how` | True | `correct` | `correct` |
| `audit-003` | `time-complexity-intro` | `ex1-long-why` | True | `correct` | `correct` |
| `audit-004` | `space-complexity-intro` | `ex1-short-how` | True | `correct` | `correct` |
| `audit-005` | `conditional-invariants` | `ex1-long-how` | True | `correct` | `correct` |
