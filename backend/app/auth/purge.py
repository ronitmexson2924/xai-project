"""Purge job for deleted accounts (D11): removes a soft-deleted user and, through the foreign
keys' ON DELETE CASCADE, all of their learning data once the retention period has passed.

    python -m app.auth.purge --retention-days 30 [--dry-run]
"""

import argparse
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import models as m


def purge_deleted_users(session: Session, retention_days: int = 30, dry_run: bool = False) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    due = m.User.deleted_at.is_not(None) & (m.User.deleted_at <= cutoff)
    if dry_run:
        return session.scalar(select(func.count()).select_from(m.User).where(due)) or 0
    result = session.execute(delete(m.User).where(due))
    return result.rowcount or 0


def main() -> None:
    from app.db.session import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as session:
        count = purge_deleted_users(session, args.retention_days, args.dry_run)
        if not args.dry_run:
            session.commit()
    verb = "would purge" if args.dry_run else "purged"
    print(f"{verb} {count} deleted account(s) older than {args.retention_days} days")


if __name__ == "__main__":
    main()
