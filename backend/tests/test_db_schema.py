"""R0: every table accepts and returns a row."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m


def test_one_row_per_table(db: Session) -> None:
    user_id, rec_id, exp_id, variant_id = (uuid.uuid4() for _ in range(4))
    now = datetime.now(UTC)
    card = {"definition": "d", "key_idea": "k", "worked_example": "w", "pitfall": "p"}
    rows: list[m.Base] = [
        m.User(id=user_id, email="a@example.com", password_hash="x", display_name="A"),
        m.ExperimentAssignment(user_id=user_id, arm="closed_loop"),
        m.ConceptRow(id="c1", name="C1", cluster="basics", description="", difficulty=1, card=card),
        m.ConceptRow(id="c2", name="C2", cluster="basics", description="", difficulty=2, card=card),
        m.ConceptEdgeRow(src="c1", dst="c2"),
        m.MisconceptionRow(id="m1", concept_id="c1", description="wrong idea"),
        m.ItemRow(id="i1", concept_id="c1", kind="mcq", stem="?", options=["a", "b"], answer="a"),
        m.QuestionnaireItemRow(id="q1", trait="persistence", item_text="I finish", source="custom"),
        m.LearnerConceptStateRow(user_id=user_id, concept_id="c1", p_mastery=0.3),
        m.LearnerTraitsRow(user_id=user_id, traits={}, bandit={}),
        m.LearnerAffectRow(user_id=user_id),
        m.QuestionnaireResponseRow(user_id=user_id, item_id="q1", value=4),
        m.StateUpdateRow(user_id=user_id, source="attempt", source_id="s1", delta={}),
        m.RecommendationRow(
            id=rec_id,
            user_id=user_id,
            kind="practice_item",
            target_concept_id="c1",
            item_id="i1",
            reasons=[],
            policy_version="t",
        ),
        m.ExplanationVariantRow(
            id=variant_id,
            concept_id="c1",
            style_key="ex1-short-how",
            body_markdown="b",
            prompt_version="p1",
            review_status="auto_ok",
        ),
        m.ExplanationRow(
            id=exp_id,
            recommendation_id=rec_id,
            user_id=user_id,
            concept_ids=["c1"],
            style={},
            style_source="generic",
            body_markdown="b",
            source="precomputed",
            variant_id=variant_id,
            prompt_version="p1",
        ),
        m.AttemptRow(
            user_id=user_id,
            item_id="i1",
            recommendation_id=rec_id,
            explanation_id=exp_id,
            response="a",
            correct=True,
            latency_ms=1200,
        ),
        m.ExplanationEventRow(
            idempotency_key=uuid.uuid4(),
            explanation_id=exp_id,
            user_id=user_id,
            type="shown",
            client_ts=now,
        ),
        m.ExplanationFeedbackRow(explanation_id=exp_id, summary={"effective_dwell_ms": 0}),
    ]
    for row in rows:  # flush one at a time so foreign keys resolve in order
        db.add(row)
        db.flush()

    expected = {
        m.User: 1,
        m.ConceptRow: 2,
        m.ItemRow: 1,
        m.ExplanationEventRow: 1,
        m.ExplanationFeedbackRow: 1,
    }
    for model, count in expected.items():
        assert db.scalar(select(func.count()).select_from(model)) == count

    state = db.get(m.LearnerConceptStateRow, (user_id, "c1"))
    assert state is not None
    assert state.misconception_ids == [] and state.streak == 0
    assert db.get(m.ItemRow, "i1").review_status == "draft"
    assert {t.name for t in m.Base.metadata.sorted_tables} == {type(r).__tablename__ for r in rows}
