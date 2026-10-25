"""Account soft-deletion purge job (D11 privacy compliance).

Owner: Mit.
Erases PII for accounts that have been soft-deleted past the retention period.
"""

import argparse
from datetime import UTC, datetime, timedelta

from app.auth.store import InMemoryUserStore, auth_store


def purge_soft_deleted_users(
    store: InMemoryUserStore | None = None,
    retention_days: int = 0,
    dry_run: bool = False,
) -> int:
    """Purges PII for soft-deleted users past retention window."""
    target_store = store or auth_store
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=retention_days)

    purged_count = 0

    with target_store._lock:
        to_purge: list = []
        for user in list(target_store._users_by_id.values()):
            if user.deleted_at is not None and user.deleted_at <= cutoff:
                to_purge.append(user)

        for user in to_purge:
            if dry_run:
                purged_count += 1
                continue

            # Remove from email index
            if user.email in target_store._users_by_email:
                del target_store._users_by_email[user.email]

            # Redact personal identifiers in user record
            user.display_name = f"[Purged User {str(user.id)[:8]}]"
            user.email = f"purged_{str(user.id)}@purged.local"
            user.password_hash = ""

            purged_count += 1

    return purged_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge soft-deleted user accounts.")
    parser.add_argument(
        "--retention-days",
        type=int,
        default=0,
        help="Number of days soft-deleted accounts are retained before purge (default: 0).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate purge without mutating records.",
    )

    args = parser.parse_args()
    count = purge_soft_deleted_users(
        retention_days=args.retention_days,
        dry_run=args.dry_run,
    )
    mode_str = "[DRY RUN] Would purge" if args.dry_run else "Successfully purged"
    print(f"{mode_str} {count} soft-deleted user accounts (retention={args.retention_days} days).")


if __name__ == "__main__":
    main()
