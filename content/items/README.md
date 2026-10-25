# content/items/ (owner: Mit, task M5; reviewer: Ronit)

One YAML file per cluster, e.g. `recursion.yaml`:

```yaml
items:
  - id: rbc-1
    concept_id: recursion-base-case
    kind: mcq              # mcq | short | code_trace
    stem: "What does fact(0) return?"
    options: ["0", "1", "It never returns"]
    answer: "1"
    difficulty: 2
    distractor_misconceptions: {"It never returns": recursion-no-base-case}
    is_microcheck: true
    review_status: draft   # draft -> approved (by the reviewer) | rejected
```

`pretest.yaml` and `posttest.yaml` hold the 15-item parallel tests. Their item IDs **must** start with
`pretest-` / `posttest-`: the graph never serves those items in sessions, and the analysis (R8)
recognises them by the prefix. Store answers with `LearnerModel.record_test_attempt(...)`, never
`apply_attempt`, so tests measure learning without changing the learner model.

## Current bank (M5 draft)

One file per cluster plus `pretest.yaml` / `posttest.yaml`: 282 MCQs in total. Every concept in
`concepts.yaml` has 3 practice items (`<concept>-p1..p3`, rising difficulty) and 1 micro-check
(`<concept>-mc`). Every wrong option maps to a misconception **of the item's own concept**, so a wrong
answer always tells the learner model which misconception it points to. Items whose stem ends with
"What does this print?" are graded by running their code (`backend/tests/test_items.py`), so their
answer keys cannot drift from Python's real output.

All items are `review_status: draft`. Only `approved` items are served, so the reviewer (Ronit, S3)
must set each item to `approved` or `rejected` before the pilot. `pretest-NN` and `posttest-NN` are
parallel: same concept, same difficulty, different surface details.

## How to review (S3)

From `backend/`:

```bash
python -m app.graph.review --stats                  # what is approved, and is the bank ready?
python -m app.graph.review --cluster recursion      # walk through drafts: a / r / s / q
python -m app.graph.seed ../content                 # load the decisions into the database
```

Each item is shown with its answer and the misconception behind every wrong option. Approve an item
only if the key is right **and** each wrong option really is the mistake it is mapped to. The bank is
ready for the pilot when `--stats` says so: at least 180 approved practice items, every concept with
an approved practice item and micro-check, and both tests fully approved.
