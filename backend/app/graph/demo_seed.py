"""Create three demo learners with interesting states, by running the real services.

    python -m app.graph.demo_seed [--password PW]   (from backend/, after app.graph.seed)

For local development and demos only; never run it against the pilot database. With --password
the demo accounts can log in (asha@demo.example.com, ben@..., chen@...); without it they cannot.
It is idempotent:
existing demo learners are deleted and rebuilt. Concepts without approved items get clearly
labelled draft placeholder items so the demo works before the real item bank (M5) exists.

- Asha (closed loop): new learner; questionnaire says example-first, short explanations.
- Ben (static): basics fine, but a misconception on recursion base cases and a prerequisite gap.
- Chen (closed loop): advanced; explanation feedback has taught the system rule-first + "why".
"""

import sys
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.contracts.explanation import ExplanationFeedbackSummary, StyleParams
from app.contracts.learner import AttemptRecord, ExperimentArm
from app.db import models as m
from app.graph.service import GraphSnapshot
from app.learner_model.service import LearnerModel
from app.planner.service import Planner

DEMO_DOMAIN = "@demo.example.com"  # reserved for documentation (RFC 2606), accepted at login
NO_LOGIN = "!demo-account-no-login"
PLACEHOLDER_PREFIX = "demo-placeholder-"
DONT_KNOW = "(no answer)"
START = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def _clock() -> Iterator[datetime]:
    t = START
    while True:
        yield t
        t += timedelta(minutes=2)


def ensure_items(session: Session, concept_ids: list[str]) -> None:
    """Give each concept without an approved practice item a draft placeholder MCQ and
    micro-check."""
    have = set(
        session.scalars(
            select(m.ItemRow.concept_id).where(
                m.ItemRow.review_status == "approved", m.ItemRow.is_microcheck.is_(False)
            )
        )
    )
    for concept_id in concept_ids:
        if concept_id in have:
            continue
        first_misconception = session.scalar(
            select(m.MisconceptionRow.id)
            .where(m.MisconceptionRow.concept_id == concept_id)
            .order_by(m.MisconceptionRow.id)
        )
        for suffix, microcheck in (("q", False), ("check", True)):
            item_id = f"{PLACEHOLDER_PREFIX}{concept_id}-{suffix}"
            if session.get(m.ItemRow, item_id) is None:
                session.add(
                    m.ItemRow(
                        id=item_id,
                        concept_id=concept_id,
                        kind="mcq",
                        stem=f"[demo placeholder] Question on {concept_id}",
                        options=["right", "wrong (misconception)", "wrong"],
                        answer="right",
                        distractor_misconceptions=(
                            {"wrong (misconception)": first_misconception}
                            if first_misconception
                            else {}
                        ),
                        is_microcheck=microcheck,
                        review_status="draft",
                    )
                )
    session.flush()


class DemoLearner:
    def __init__(
        self,
        session: Session,
        graph: GraphSnapshot,
        name: str,
        arm: ExperimentArm,
        password_hash: str = NO_LOGIN,
    ):
        self.session, self.graph = session, graph
        self.user_id = uuid.uuid4()
        session.add(
            m.User(
                id=self.user_id,
                email=f"{name.lower()}{DEMO_DOMAIN}",
                password_hash=password_hash,
                display_name=f"{name} (demo)",
                consent_at=START,
            )
        )
        session.flush()
        session.add(m.ExperimentAssignment(user_id=self.user_id, arm=arm))
        session.flush()
        self.model = LearnerModel(session, graph)
        self.planner = Planner(session, graph, self.model, seed=7, now=lambda: START)
        self.clock = _clock()

    def questionnaire(self, levels: dict[str, int]) -> None:
        items = self.model.questionnaire_items()
        self.model.init_from_questionnaire(
            self.user_id,
            {i.id: (6 - levels[i.trait] if i.reverse_scored else levels[i.trait]) for i in items},
        )

    def answer(self, concept_id: str, correct: bool, misconception: bool = False) -> None:
        item = self.graph.items_for_concept(concept_id)[0]
        wrong = [o for o in item.options if o != item.answer]
        mapped = [o for o in wrong if o in item.distractor_misconceptions]
        unmapped = [o for o in wrong if o not in item.distractor_misconceptions]
        if correct:
            response = item.answer
        elif misconception:
            response = (mapped or wrong)[0]
        else:  # a slip, not a misconception: real items map every distractor
            response = unmapped[-1] if unmapped else DONT_KNOW
        self.model.apply_attempt(
            AttemptRecord(
                id=uuid.uuid4(),
                user_id=self.user_id,
                item_id=item.id,
                concept_id=concept_id,
                response=response,
                correct=correct,
                latency_ms=12_000,
                confidence=4 if correct else 2,
                created_at=next(self.clock),
            )
        )

    def explanation_feedback(self, style: StyleParams, clarity: int, followup_correct: bool):
        state = self.model.get_state(self.user_id)
        rec = self.planner.next_step(state)
        explanation_id = uuid.uuid4()
        self.session.add(
            m.ExplanationRow(
                id=explanation_id,
                recommendation_id=rec.id,
                user_id=self.user_id,
                concept_ids=[rec.target_concept_id],
                style=style.model_dump(),
                style_source="exploration",
                body_markdown="[demo explanation]",
                source="template",
                prompt_version="demo",
            )
        )
        self.session.flush()
        self.model.apply_explanation_feedback(
            ExplanationFeedbackSummary(
                explanation_id=explanation_id,
                user_id=self.user_id,
                concept_ids=[rec.target_concept_id],
                style=style,
                style_source="exploration",
                effective_dwell_ms=40_000,
                clarity_rating=clarity,
                followup_correct=followup_correct,
            )
        )


BASICS = ["variables-and-types", "conditionals", "loops", "functions"]
ARRAYS = ["arrays-indexing", "array-traversal", "big-o-notation", "loop-complexity-analysis"]
RECURSION = ["recursion-base-case", "recursive-case"]


def build(session: Session, password_hash: str = NO_LOGIN) -> dict[str, uuid.UUID]:
    session.execute(delete(m.User).where(m.User.email.like(f"%{DEMO_DOMAIN}")))
    ensure_items(session, BASICS + ARRAYS + RECURSION + ["references", "two-pointers"])
    graph = GraphSnapshot.from_db(session, include_drafts=True)

    asha = DemoLearner(session, graph, "Asha", "closed_loop", password_hash)
    asha.questionnaire(
        {
            "abstraction_preference": 1,
            "load_tolerance": 2,
            "depth_preference": 3,
            "persistence": 4,
            "self_efficacy": 2,
        }
    )
    for concept_id, correct in (("variables-and-types", True), ("loops", False)):
        asha.answer(concept_id, correct)

    ben = DemoLearner(session, graph, "Ben", "static_personalized", password_hash)
    ben.questionnaire(_neutral())
    for concept_id in BASICS:
        for _ in range(3):
            ben.answer(concept_id, True)
    ben.answer("recursion-base-case", False, misconception=True)
    ben.answer("recursive-case", False)
    ben.answer("recursive-case", False)

    chen = DemoLearner(session, graph, "Chen", "closed_loop", password_hash)
    chen.questionnaire(_neutral())
    for concept_id in BASICS + ARRAYS + RECURSION:
        for _ in range(4):
            chen.answer(concept_id, True)
    rule_first_why = StyleParams(example_first=False, length="long", depth="why")
    example_how = StyleParams(example_first=True, length="short", depth="how")
    for _ in range(12):
        chen.explanation_feedback(rule_first_why, clarity=5, followup_correct=True)
        chen.explanation_feedback(example_how, clarity=2, followup_correct=False)
    return {"asha": asha.user_id, "ben": ben.user_id, "chen": chen.user_id}


def _neutral() -> dict[str, int]:
    return {
        t: 3
        for t in (
            "abstraction_preference",
            "load_tolerance",
            "depth_preference",
            "persistence",
            "self_efficacy",
        )
    }


def main() -> int:
    import argparse

    from app.auth.security import hash_password
    from app.db.session import SessionLocal

    parser = argparse.ArgumentParser(description="Create the demo learners (development only).")
    parser.add_argument("--password", help="let the demo accounts log in with this password")
    args = parser.parse_args()
    password_hash = hash_password(args.password) if args.password else NO_LOGIN

    with SessionLocal() as session:
        users = build(session, password_hash)
        session.commit()
        graph = GraphSnapshot.from_db(session, include_drafts=True)
        model = LearnerModel(session, graph)
        planner = Planner(session, graph, model, now=lambda: START)
        for name, user_id in users.items():
            state = model.get_state(user_id)
            rec = planner.next_step(state)
            traits = ", ".join(f"{t}={e.mean:.2f}" for t, e in state.traits.traits.items())
            print(
                f"{name}: {state.total_attempts} attempts; next = {rec.kind} "
                f"{rec.target_concept_id} ({rec.reasons[0].code}); {traits}"
            )
        session.rollback()  # the inspection above created recommendations; don't keep them
    return 0


if __name__ == "__main__":
    sys.exit(main())
