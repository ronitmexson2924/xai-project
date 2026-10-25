"""Show every learner-facing explanation (docs/XAI_DESIGN.md E1-E5) for the three demo learners.

    python -m app.planner.xai_demo      (from backend/, after seeding content with app.graph.seed)

Runs inside a transaction that is rolled back, so the database is left unchanged.
"""

import sys
import textwrap
import uuid
from datetime import UTC, datetime

from app.contracts.learner import AttemptRecord
from app.graph.demo_seed import START, build
from app.graph.service import GraphSnapshot
from app.learner_model.service import LearnerModel
from app.planner.service import Planner
from app.planner.xai import Explainability

WIDTH = 92


def say(label: str, text: str, indent: int = 2) -> None:
    prefix = " " * indent + f"{label:<10}"
    print(textwrap.fill(text, WIDTH, initial_indent=prefix, subsequent_indent=" " * len(prefix)))


def main() -> int:
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        try:
            users = build(session)
            graph = GraphSnapshot.from_db(session, include_drafts=True)
            model = LearnerModel(session, graph)
            planner = Planner(session, graph, model, seed=1, now=lambda: START)
            xai = Explainability(model)
            for name, user_id in users.items():
                state = model.get_state(user_id)
                rec = planner.next_step(state)
                planner.choose_style(state, rec.target_concept_id)
                why = xai.why(rec.id)
                concept = graph.get_concept(rec.target_concept_id).name
                print(f"\n{'=' * WIDTH}\n{name.upper()} ({state.arm}): next = {concept}\n")
                say("WHY", why.rationale.summary)
                if why.rationale.alternative:
                    say("OTHERWISE", why.rationale.alternative)
                for cf in why.rationale.counterfactuals:
                    say("WHAT IF", f"{cf.condition} → {cf.outcome}.")
                say("STYLE", f"{why.style.summary} [{why.style.confidence}]")
                for subject in ("abstraction_preference", "load_tolerance", rec.target_concept_id):
                    belief = xai.explain_belief(user_id, subject)
                    say("BELIEF", f"{belief.label}: {belief.summary} [{belief.confidence}]")
                    for evidence in belief.top_evidence[:2]:
                        say("", f"- {evidence}", indent=4)
                item = graph.items_for_concept(rec.target_concept_id)[0]
                delta = model.apply_attempt(
                    AttemptRecord(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        item_id=item.id,
                        concept_id=item.concept_id,
                        response=item.answer,
                        correct=True,
                        latency_ms=9000,
                        created_at=datetime.now(UTC),
                    )
                )
                for message in xai.explain_change(delta).messages or ["(nothing worth telling)"]:
                    say("AFTER", f"a correct answer: {message}")
        finally:
            session.rollback()
    return 0


if __name__ == "__main__":
    sys.exit(main())
