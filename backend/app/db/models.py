"""SQLAlchemy models for every table in docs/DATA_MODEL.md.

JSONB columns hold payloads shaped like the Pydantic models in app/contracts/.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB, uuid.UUID: UUID(as_uuid=True)}


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def _user_fk(primary_key: bool = False) -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=primary_key)


# --- Identity & experiment (owner: Mit) ---------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = _now()
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # tokens issued before this instant are rejected (logout, account deletion)
    tokens_valid_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExperimentAssignment(Base):
    __tablename__ = "experiment_assignments"
    __table_args__ = (
        CheckConstraint("arm IN ('generic','static_personalized','closed_loop')", name="arm_valid"),
    )

    user_id: Mapped[uuid.UUID] = _user_fk(primary_key=True)
    arm: Mapped[str] = mapped_column(Text)
    assigned_at: Mapped[datetime] = _now()


# --- Concept graph & content (owner: Ronit; items: Mit) -----------------------------------------


class ConceptRow(Base):
    __tablename__ = "concepts"
    __table_args__ = (CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty_range"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    cluster: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(SmallInteger)
    card: Mapped[dict[str, Any]]


class ConceptEdgeRow(Base):
    __tablename__ = "concept_edges"
    __table_args__ = (CheckConstraint("src <> dst", name="no_self_loop"),)

    src: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True
    )
    dst: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True
    )
    weight: Mapped[float] = mapped_column(Float, server_default=text("0.8"))


class MisconceptionRow(Base):
    __tablename__ = "misconceptions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(Text)
    remediation_hint: Mapped[str] = mapped_column(Text, server_default="")


class ItemRow(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("kind IN ('mcq','short','code_trace')", name="kind_valid"),
        CheckConstraint(
            "review_status IN ('draft','approved','rejected')", name="review_status_valid"
        ),
        Index("ix_items_concept", "concept_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list[Any]] = mapped_column(server_default=text("'[]'::jsonb"))
    answer: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(SmallInteger, server_default=text("2"))
    distractor_misconceptions: Mapped[dict[str, Any]] = mapped_column(
        server_default=text("'{}'::jsonb")
    )
    is_microcheck: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    review_status: Mapped[str] = mapped_column(Text, server_default="draft")


class QuestionnaireItemRow(Base):
    __tablename__ = "questionnaire_items"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    trait: Mapped[str] = mapped_column(Text)
    # Column is "text"; the attribute is renamed because `text` would shadow sqlalchemy.text here.
    item_text: Mapped[str] = mapped_column("text", Text)
    reverse_scored: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    source: Mapped[str] = mapped_column(Text)


# --- Learner state (owner: Ronit) ---------------------------------------------------------------


class LearnerConceptStateRow(Base):
    __tablename__ = "learner_concept_state"

    user_id: Mapped[uuid.UUID] = _user_fk(primary_key=True)
    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True
    )
    p_mastery: Mapped[float] = mapped_column(Float)
    n_attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    # > 0: consecutive correct attempts, < 0: consecutive wrong attempts
    streak: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    misconception_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    misconception_suspicion: Mapped[float] = mapped_column(Float, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearnerTraitsRow(Base):
    __tablename__ = "learner_traits"

    user_id: Mapped[uuid.UUID] = _user_fk(primary_key=True)
    traits: Mapped[dict[str, Any]]
    bandit: Mapped[dict[str, Any]]
    version: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearnerAffectRow(Base):
    __tablename__ = "learner_affect"

    user_id: Mapped[uuid.UUID] = _user_fk(primary_key=True)
    engagement: Mapped[float] = mapped_column(Float, server_default=text("0.5"))
    frustration: Mapped[float] = mapped_column(Float, server_default=text("0"))
    fatigue: Mapped[float] = mapped_column(Float, server_default=text("0"))
    session_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class QuestionnaireResponseRow(Base):
    __tablename__ = "questionnaire_responses"
    __table_args__ = (CheckConstraint("value BETWEEN 1 AND 5", name="likert_range"),)

    user_id: Mapped[uuid.UUID] = _user_fk(primary_key=True)
    item_id: Mapped[str] = mapped_column(
        ForeignKey("questionnaire_items.id", ondelete="CASCADE"), primary_key=True
    )
    value: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = _now()


class StateUpdateRow(Base):
    __tablename__ = "state_updates"
    __table_args__ = (
        CheckConstraint(
            "source IN ('attempt','explanation_feedback','questionnaire')", name="source_valid"
        ),
        UniqueConstraint("source", "source_id", name="uq_state_updates_source"),
        Index("ix_state_updates_user_created", "user_id", text("created_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = _user_fk()
    source: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(Text)
    delta: Mapped[dict[str, Any]]
    created_at: Mapped[datetime] = _now()


# --- Session activity (owner: Ronit for recommendations/attempts, Mit for explanations) ---------


class RecommendationRow(Base):
    __tablename__ = "recommendations"
    __table_args__ = (Index("ix_recommendations_user_created", "user_id", text("created_at DESC")),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    kind: Mapped[str] = mapped_column(Text)
    target_concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"))
    item_id: Mapped[str | None] = mapped_column(ForeignKey("items.id"))
    reasons: Mapped[list[Any]]
    policy_version: Mapped[str] = mapped_column(Text)
    # XAI: built when the decision is made, so "why" shows exactly the reasoning used
    rationale: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # contracts.xai.Rationale
    style_rationale: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # StyleRationale
    created_at: Mapped[datetime] = _now()


class ExplanationVariantRow(Base):
    __tablename__ = "explanation_variants"
    __table_args__ = (
        UniqueConstraint("concept_id", "style_key", "prompt_version", name="uq_variant"),
        CheckConstraint(
            "review_status IN ('auto_ok','approved','rejected')", name="review_status_valid"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"))
    style_key: Mapped[str] = mapped_column(Text)
    body_markdown: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    validation: Mapped[dict[str, Any]] = mapped_column(server_default=text("'{}'::jsonb"))
    review_status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()


class ExplanationRow(Base):
    __tablename__ = "explanations"
    __table_args__ = (
        CheckConstraint("source IN ('precomputed','llm','template')", name="source_valid"),
        Index("uq_explanations_recommendation", "recommendation_id", unique=True),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = _user_fk()
    concept_ids: Mapped[list[str]] = mapped_column(ARRAY(Text))
    style: Mapped[dict[str, Any]]
    style_source: Mapped[str] = mapped_column(Text)
    body_markdown: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("explanation_variants.id"))
    followup_item_id: Mapped[str | None] = mapped_column(ForeignKey("items.id"))
    prompt_version: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = _now()


class AttemptRow(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        Index("ix_attempts_user_created", "user_id", text("created_at DESC")),
        # a recommendation is answered at most once: replays cannot farm mastery
        Index(
            "uq_attempts_recommendation",
            "recommendation_id",
            unique=True,
            postgresql_where=text("recommendation_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id"))
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL")
    )
    explanation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("explanations.id", ondelete="SET NULL")
    )
    response: Mapped[str] = mapped_column(Text)
    correct: Mapped[bool] = mapped_column(Boolean)
    latency_ms: Mapped[int] = mapped_column(Integer)
    hints_used: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    confidence: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = _now()


class ExplanationEventRow(Base):
    __tablename__ = "explanation_events"
    __table_args__ = (Index("ix_explanation_events_explanation", "explanation_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(unique=True)
    explanation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("explanations.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = _user_fk()
    type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(server_default=text("'{}'::jsonb"))
    client_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    server_ts: Mapped[datetime] = _now()


class ExplanationFeedbackRow(Base):
    __tablename__ = "explanation_feedback"

    explanation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("explanations.id", ondelete="CASCADE"), primary_key=True
    )
    summary: Mapped[dict[str, Any]]
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
