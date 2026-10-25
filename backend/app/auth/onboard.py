"""Pilot account provisioning (Task M8).

Owner: Mit.

    python -m app.auth.onboard cohort --count 45 --domain study.edu --output-csv roster.csv
    python -m app.auth.onboard admin --email you@uni.edu      (asks for the password)

`cohort` creates participant accounts with balanced, randomised arms (the same allocation as
self-registration) and writes their temporary passwords to a CSV for the study coordinator. The CSV
holds credentials: keep it out of git (*.roster.csv is ignored) and delete it after hand-out.
`admin` creates the account that may open /admin and the research export.
"""

import argparse
import csv
import getpass
import secrets
import string
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.auth.models import MIN_PASSWORD_LENGTH
from app.auth.security import hash_password
from app.auth.store import UserAlreadyExistsError, register_user

PASSWORD_SYMBOLS = "!@#$%^&*"


def generate_secure_password(length: int = 14) -> str:
    """A random password with upper- and lower-case letters, a digit and a symbol."""
    alphabet = string.ascii_letters + string.digits + PASSWORD_SYMBOLS
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in PASSWORD_SYMBOLS for c in password)
        ):
            return password


def onboard_cohort(
    session: Session,
    count: int,
    email_prefix: str = "participant",
    domain: str = "study.edu",
    csv_output_path: Path | None = None,
) -> list[dict[str, str]]:
    participants = []
    for i in range(1, count + 1):
        email = f"{email_prefix}_{i:03d}@{domain}"
        password = generate_secure_password()
        try:
            user, arm = register_user(session, email, hash_password(password), f"Student {i:03d}")
        except UserAlreadyExistsError:
            continue  # re-running the command only adds the missing accounts
        participants.append(
            {"user_id": str(user.id), "email": email, "temporary_password": password, "arm": arm}
        )
    if csv_output_path and participants:
        csv_output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(participants[0]))
            writer.writeheader()
            writer.writerows(participants)
    return participants


def create_admin(session: Session, email: str, password: str, display_name: str = "Admin") -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    register_user(
        session, email, hash_password(password), display_name, arm="generic", is_admin=True
    )


def main() -> int:
    from app.db.session import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    cohort = sub.add_parser("cohort", help="create participant accounts")
    cohort.add_argument("--count", type=int, default=45)
    cohort.add_argument("--prefix", default="participant")
    cohort.add_argument("--domain", default="study.edu")
    cohort.add_argument("--output-csv", type=Path, default=Path("pilot.roster.csv"))
    admin = sub.add_parser("admin", help="create an administrator account")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", default="Admin")
    args = parser.parse_args()

    with SessionLocal() as session:
        if args.command == "cohort":
            results = onboard_cohort(session, args.count, args.prefix, args.domain, args.output_csv)
            session.commit()
            print(f"Created {len(results)} accounts; credentials in {args.output_csv}")
        else:
            password = getpass.getpass("Admin password: ")
            try:
                create_admin(session, args.email, password, args.name)
            except (ValueError, UserAlreadyExistsError) as err:
                print(f"error: {err}", file=sys.stderr)
                return 1
            session.commit()
            print(f"Created admin {args.email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
