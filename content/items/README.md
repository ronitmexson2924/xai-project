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

`pretest.yaml` and `posttest.yaml` hold the 15-item parallel tests. They are never served in sessions.
