"""User accounts and experiment assignment, stored in Postgres (users, experiment_assignments).

Owner: Mit. Every function takes the request's Session and flushes; the request commits.
"""

import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import ALL_ARMS, ExperimentArm
from app.db import models as m

# any fixed 64-bit key: serialises arm assignment so concurrent sign-ups stay balanced
_ARM_LOCK_KEY = 0x50434741524D


class UserAlreadyExistsError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


def normalise_email(email: str) -> str:
    return email.strip().lower()


def choose_arm(session: Session) -> ExperimentArm:
    """Balanced randomisation: the arm with the fewest learners, ties broken at random. Holds a
    transaction-level advisory lock so two concurrent sign-ups cannot both see the same counts."""
    session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ARM_LOCK_KEY})
    counts = dict(
        session.execute(
            select(m.ExperimentAssignment.arm, func.count())
            .join(m.User, m.User.id == m.ExperimentAssignment.user_id)
            .where(m.User.is_admin.is_(False))
            .group_by(m.ExperimentAssignment.arm)
        ).all()
    )
    fewest = min(counts.get(arm, 0) for arm in ALL_ARMS)
    return secrets.choice([arm for arm in ALL_ARMS if counts.get(arm, 0) == fewest])


def register_user(
    session: Session,
    email: str,
    password_hash: str,
    display_name: str,
    arm: ExperimentArm | None = None,
    is_admin: bool = False,
) -> tuple[m.User, ExperimentArm]:
    email = normalise_email(email)
    if session.scalar(select(m.User.id).where(m.User.email == email)) is not None:
        raise UserAlreadyExistsError(email)
    chosen = arm or choose_arm(session)
    user = m.User(
        id=uuid4(),
        email=email,
        password_hash=password_hash,
        display_name=display_name.strip(),
        is_admin=is_admin,
    )
    try:
        with session.begin_nested():
            session.add(user)
            session.flush()
    except IntegrityError:  # lost a race with a concurrent registration of the same email
        raise UserAlreadyExistsError(email) from None
    session.add(m.ExperimentAssignment(user_id=user.id, arm=chosen))
    session.flush()
    return user, chosen


def get_active_user(session: Session, user_id: UUID) -> tuple[m.User, ExperimentArm] | None:
    row = session.execute(
        select(m.User, m.ExperimentAssignment.arm)
        .outerjoin(m.ExperimentAssignment, m.ExperimentAssignment.user_id == m.User.id)
        .where(m.User.id == user_id, m.User.deleted_at.is_(None))
    ).one_or_none()
    if row is None:
        return None
    return row[0], row[1] or "generic"


def get_user_by_email(session: Session, email: str) -> m.User | None:
    return session.scalar(
        select(m.User).where(m.User.email == normalise_email(email), m.User.deleted_at.is_(None))
    )


def set_consent(session: Session, user: m.User) -> datetime:
    if user.consent_at is None:  # consent is recorded once; repeating it keeps the first time
        user.consent_at = datetime.now(UTC)
        session.flush()
    return user.consent_at


def revoke_tokens(session: Session, user: m.User) -> None:
    """Invalidate every token issued so far (logout everywhere)."""
    user.tokens_valid_after = datetime.now(UTC).replace(microsecond=0)
    session.flush()


def soft_delete_user(session: Session, user: m.User) -> None:
    """Withdraw: the account stops working now; app.auth.purge erases its data later."""
    now = datetime.now(UTC)
    user.deleted_at = now
    user.tokens_valid_after = now.replace(microsecond=0)
    session.flush()
