"""R7: the demo seed builds three learners in the intended states, idempotently."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contracts.reasons import ReasonCode
from app.db import models as m
from app.graph.demo_seed import DEMO_DOMAIN, build
from app.graph.service import GraphSnapshot
from app.learner_model.service import LearnerModel
from app.planner.service import Planner


def test_demo_learners(seeded: Session) -> None:
    build(seeded)
    users = build(seeded)  # rebuilding replaces the previous demo learners
    demo_count = (
        select(func.count()).select_from(m.User).where(m.User.email.like(f"%{DEMO_DOMAIN}"))
    )
    assert seeded.scalar(demo_count) == 3

    graph = GraphSnapshot.from_db(seeded, include_drafts=True)
    model = LearnerModel(seeded, graph)
    planner = Planner(seeded, graph, model)

    asha = model.get_state(users["asha"])
    assert asha.traits.traits["abstraction_preference"].mean < 0.2  # example-first

    ben = model.get_state(users["ben"])
    assert ben.mastery["recursion-base-case"].misconception_ids
    rec = planner.next_step(ben)
    assert (rec.target_concept_id, rec.reasons[0].code) == (
        "recursion-base-case",
        ReasonCode.MISCONCEPTION_DETECTED,
    )

    chen = model.get_state(users["chen"]).traits.traits
    assert chen["abstraction_preference"].mean > 0.6  # learned rule-first from feedback
    assert chen["depth_preference"].mean > 0.6
    assert chen["abstraction_preference"].n_observations == 24
