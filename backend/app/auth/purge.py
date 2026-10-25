"""Account purge job (D11 delete-my-data).

Owner: Mit.

    python -m app.auth.purge [--retention-days N] [--dry-run]

Withdrawn accounts (DELETE /me) stop working at once; this job then deletes them for good. Every
learner table references users with ON DELETE CASCADE, so the user's attempts, explanations,
events, questionnaire answers and model state go with the account.
"""

import argparse
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import models as m


def purge_soft_deleted_users(
    session: Session, retention_days: int = 0, dry_run: bool = False
) -> int:
    """Delete accounts withdrawn more than `retention_days` ago. Returns how many."""
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    due = m.User.deleted_at.is_not(None) & (m.User.deleted_at <= cutoff)
    count = session.scalar(select(func.count()).select_from(m.User).where(due)) or 0
    if not dry_run and count:
        session.execute(delete(m.User).where(due))
        session.flush()
    return count


def main() -> None:
    from app.db.session import SessionLocal

    parser = argparse.ArgumentParser(description="Delete withdrawn learner accounts.")
    parser.add_argument("--retention-days", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as session:
        count = purge_soft_deleted_users(session, args.retention_days, args.dry_run)
        session.commit()
    verb = "Would delete" if args.dry_run else "Deleted"
    print(f"{verb} {count} withdrawn account(s) (retention {args.retention_days} days).")


if __name__ == "__main__":
    main()
