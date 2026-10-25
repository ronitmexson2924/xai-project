# Content review checklist (R1a / R1b, and the R3 questionnaire)

All content in this folder was **drafted by Ronit's coding agent**. It must be reviewed by a person
before the pilot: Ronit first, then Mit cross-reviews (S3). Tick R1a/R1b in `tasks/ronit.md` only
after your own review.

## Already checked automatically (CI)

`backend/tests/test_content.py` and `test_graph.py` check that:

- all 63 concepts have complete cards;
- every **worked example runs**, and its printed output matches the comments (checked by
  hand once);
- the prerequisites form a DAG with no unknown IDs;
- **no prerequisite is harder than the concept that needs it**;
- every concept has ≥ 1 misconception, and ≥ 2 for the recursion, reference and complexity
  concepts (97 in total);
- every questionnaire trait has ≥ 3 items and a reverse-scored one;
- seeding is idempotent.

## What only a person can check (per concept, about 2 minutes each)

- [ ] **Definition**: correct, and at the right level for 2nd/3rd-year students?
- [ ] **Key idea**: is it *the* idea a student must get? (The explainer builds on it.)
- [ ] **Worked example**: is it the example you would use in a lab?
- [ ] **Pitfall**: is it a mistake students actually make?
- [ ] **Prerequisites**: would you teach these first? Anything missing or unnecessary?
- [ ] **Difficulty (1–5)**: these are the agent's estimates.
- [ ] **Misconceptions**: real, and phrased as a belief the student holds? Is the
  remediation hint something a tutor would say?

Suggested split: review the `basics`, `arrays-strings` and `recursion` clusters first. They
are what the first pilot sessions reach (`R1a` needs only the first 3 concepts, `R1b` all of
them).

## Points the agent itself would question

1. **Fixed already:** `stack` and `queue` required `dynamic-arrays` (amortised analysis), and
   `overlapping-subproblems` required `recurrence-relations`. Each made a harder concept a
   prerequisite of an easier one. All three now depend on the simpler concept, and the
   deepest chain dropped from 14 to 11 levels. *The R6 simulation report was generated before
   this change; regenerate it after your review if you change the graph further.*
2. `graph-representation` requires `tree-terminology` and `hash-maps`. Is the tree prerequisite
   needed, or should graphs open straight after arrays/hash maps?
3. `union-find`: the worked example uses path halving but not union by rank, while the key
   idea mentions both. Is that fine for teaching, or should the example match the key idea?
4. The `strings-as-sequences` card says repeated concatenation "can cost O(n²)". That's true
   in general, though CPython sometimes optimises `s += ...`. Keep it simple, or add the
   nuance?
5. `recursion-tracing` uses `fib` as its example and `overlapping-subproblems` reuses it.
   Intentional (the same tree seen twice), but you may prefer a different example in one of
   them.
6. **Questionnaire (R3):** all 20 items are custom wording modelled on the cited scales
   (Short Grit Scale, NCS-18, MSLQ, cognitive-load and worked-example research). Compare them
   with the originals and decide whether to use the published items (check their licences).
7. Difficulty ratings and cluster boundaries are the agent's guesses. Item difficulty (M5)
   should be consistent with them.

## How to make changes

Edit `concepts.yaml` / `misconceptions.yaml` / `questionnaire.yaml` directly. Then run the
following from `backend/`:

```bash
pytest -q tests/test_content.py tests/test_graph.py   # validates the content
python -m app.graph.seed ../content                    # loads it into your dev database
```
