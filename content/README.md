# content/

Curated learning content, loaded into Postgres by `python -m app.graph.seed content/` (task R1).

| File | Owner | Task |
|---|---|---|
| `concepts.yaml`: concepts, prerequisites, concept cards | Ronit | R1 |
| `misconceptions.yaml` | Ronit | R1 |
| `questionnaire.yaml`: psychometric items with source citations | Ronit | R3 |
| `items/*.yaml`: question bank, micro-checks, pre/post tests | Mit | M5 |

`concepts.example.yaml` shows the exact format. Concept cards are the **only** factual source the
explainer may use, so every card must be human-reviewed (an LLM may draft it).
