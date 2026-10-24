# Psychometric Concept-Graph Explanation-Feedback Engine

Adaptive learning engine for Data Structures & Algorithms that combines a
**concept-mastery graph** with a **psychometric trait vector**, generates
**concept-level explanations shaped by that profile**, and uses the learner's
**interaction with each explanation** as a feedback signal that updates both.

## Branch model

| Branch  | Purpose                                                     | Who writes to it         |
|---------|-------------------------------------------------------------|--------------------------|
| `main`  | Stable, tested releases only (demo / submission builds)     | PR from `dev` only       |
| `dev`   | Integration branch: all code is combined and tested here    | PRs from `ronit` / `mit` |
| `ronit` | Ronit's working branch (learner model, planner, research)   | Ronit                    |
| `mit`   | Mit's working branch (explanations, telemetry, API, UI)     | Mit                      |

All project docs, agent instructions and code live on `dev`. Start there:
`git checkout dev` and read `AGENTS.md`.
