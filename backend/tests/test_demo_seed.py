"""R7: the demo seed builds three learners in the intended states, idempotently."""

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.session import PENDING_TTL
from app.contracts.reasons import ReasonCode
from app.db import models as m
from app.graph.demo_seed import DEMO_DOMAIN, build
from app.graph.service import GraphSnapshot
from app.learner_model.service import LearnerModel
from app.planner.service import Planner


def test_demo_learners(seeded: Session) -> None:
    # the real bank is all drafts until it is reviewed: demos must use those, not placeholders
    seeded.execute(
        update(m.ItemRow).where(m.ItemRow.concept_id == "loops").values(review_status="draft")
    )
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

    # placeholders only fill concepts with no real item, so learners never get one beside real ones
    rows = seeded.execute(
        select(m.ItemRow.id, m.ItemRow.concept_id).where(m.ItemRow.is_microcheck.is_(False))
    ).all()
    placeholder = {c for i, c in rows if i.startswith("demo-placeholder-")}
    real = {c for i, c in rows if not i.startswith("demo-placeholder-")}
    assert placeholder and real  # the fixture bank covers some of the demo concepts
    assert not placeholder & real
    assert "loops" in real

    chen = model.get_state(users["chen"]).traits.traits
    assert chen["abstraction_preference"].mean > 0.6  # learned rule-first from feedback
    assert chen["depth_preference"].mean > 0.6
    assert chen["abstraction_preference"].n_observations == 24


def test_demo_learners_start_on_a_real_explanation(seeded: Session) -> None:
    """The seed's past steps must not look pending, or /session would resume one of them and show
    its stub explanation instead of planning a real step."""
    users = build(seeded)
    pending = seeded.scalar(
        select(func.count())
        .select_from(m.RecommendationRow)
        .outerjoin(m.AttemptRow, m.AttemptRow.recommendation_id == m.RecommendationRow.id)
        .where(
            m.RecommendationRow.user_id.in_(list(users.values())),
            m.RecommendationRow.created_at > datetime.now(UTC) - PENDING_TTL,
            m.AttemptRow.id.is_(None),
        )
    )
    assert pending == 0
