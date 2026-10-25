"""Accounts in the database (users + experiment_assignments): registration with balanced arm
assignment, consent, and deletion (PII removed at once, rows purged later by app.auth.purge)."""

import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import ALL_ARMS, ExperimentArm, UserResponse
from app.db import models as m

ARM_LOCK = 724_001  # pg advisory lock id: one registration at a time picks an arm


class UserAlreadyExistsError(Exception):
    pass


def to_response(session: Session, user: m.User) -> UserResponse:
    arm = session.scalar(
        select(m.ExperimentAssignment.arm).where(m.ExperimentAssignment.user_id == user.id)
    )
    done = session.get(m.LearnerTraitsRow, user.id) is not None
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        arm=arm or "generic",
        consent_at=user.consent_at,
        created_at=user.created_at,
        is_admin=user.is_admin,
        questionnaire_done=done,
    )


def _choose_arm(session: Session) -> ExperimentArm:
    """The arm with the fewest learners, ties broken at random (tasks/mit.md M0)."""
    counts = dict.fromkeys(ALL_ARMS, 0)
    for arm, n in session.execute(
        select(m.ExperimentAssignment.arm, func.count()).group_by(m.ExperimentAssignment.arm)
    ):
        if arm in counts:
            counts[arm] = n
    fewest = min(counts.values())
    return secrets.choice([arm for arm, n in counts.items() if n == fewest])


def register(session: Session, email: str, password_hash: str, display_name: str) -> m.User:
    # serialise arm choice across concurrent registrations (and API workers) for balance
    session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": ARM_LOCK})
    if session.scalar(select(m.User.id).where(m.User.email == email)) is not None:
        raise UserAlreadyExistsError(email)
    user = m.User(id=uuid4(), email=email, password_hash=password_hash, display_name=display_name)
    session.add(user)
    try:
        session.flush()
    except IntegrityError as err:  # a concurrent registration with the same email won
        session.rollback()
        raise UserAlreadyExistsError(email) from err
    session.add(m.ExperimentAssignment(user_id=user.id, arm=_choose_arm(session)))
    session.flush()
    session.refresh(user)
    return user


def active_user(session: Session, user_id: UUID) -> m.User | None:
    user = session.get(m.User, user_id)
    return user if user is not None and user.deleted_at is None else None


def by_email(session: Session, email: str) -> m.User | None:
    return session.scalar(select(m.User).where(m.User.email == email, m.User.deleted_at.is_(None)))


def give_consent(session: Session, user: m.User) -> datetime:
    if user.consent_at is None:  # the first consent is the one on record
        user.consent_at = datetime.now(UTC)
    return user.consent_at


def delete_account(session: Session, user: m.User) -> None:
    """Soft delete: the account stops working at once and its identifying fields are erased
    (so the email can be registered again); learning data stays until the purge job runs."""
    user.deleted_at = datetime.now(UTC)
    user.email = f"deleted-{user.id}@deleted.invalid"
    user.display_name = "deleted"
    user.password_hash = "!deleted"
    user.is_admin = False
