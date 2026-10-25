"""Cohort onboarding and batch provisioning CLI for pilot study (Task M8).

Owner: Mit.
Provisions batches of participants with balanced experiment arm assignment
and exports credentials for study coordinators (EVALUATION_PLAN.md § Pilot protocol).
"""

import argparse
import csv
import secrets
import string
from pathlib import Path

from app.auth.models import ALL_ARMS, ExperimentArm
from app.auth.security import hash_password
from app.auth.store import InMemoryUserStore, auth_store


def generate_secure_password(length: int = 12) -> str:
    """Generates a secure temporary password containing upper, lower, digits, and special chars."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*" for c in password)
        ):
            return password


def onboard_cohort(
    count: int = 45,
    email_prefix: str = "pilot_student",
    domain: str = "dsa-pilot.edu",
    store: InMemoryUserStore | None = None,
    csv_output_path: Path | None = None,
) -> list[dict]:
    """Provisions a batch of pilot participants with balanced arm distribution."""
    target_store = store or auth_store
    participants = []

    # Cycle evenly through experiment arms
    arms_cycle: list[ExperimentArm] = list(ALL_ARMS)

    for i in range(count):
        idx = i + 1
        email = f"{email_prefix}_{idx:03d}@{domain}"
        display_name = f"Student {idx:03d}"
        temp_pwd = generate_secure_password()
        pwd_hash = hash_password(temp_pwd)

        # Balanced assignment round-robin across arms
        arm = arms_cycle[i % len(arms_cycle)]

        user, assignment = target_store.register_user(email, pwd_hash, display_name)
        assignment.arm = arm

        participant_info = {
            "user_id": str(user.id),
            "email": email,
            "display_name": display_name,
            "temporary_password": temp_pwd,
            "arm": arm,
        }
        participants.append(participant_info)

    if csv_output_path:
        csv_output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["user_id", "email", "display_name", "temporary_password", "arm"],
            )
            writer.writeheader()
            writer.writerows(participants)

    return participants


def main() -> None:
    parser = argparse.ArgumentParser(description="Onboard pilot participant cohort.")
    parser.add_argument(
        "--count",
        type=int,
        default=45,
        help="Number of participant accounts to provision (default: 45).",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="participant",
        help="Email prefix for learners.",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="study.edu",
        help="Email domain for learners.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("research/pilot_cohort_roster.csv"),
        help="Destination path for coordinator credentials CSV.",
    )

    args = parser.parse_args()
    results = onboard_cohort(
        count=args.count,
        email_prefix=args.prefix,
        domain=args.domain,
        csv_output_path=args.output_csv,
    )

    print(f"Successfully provisioned {len(results)} pilot participants.")
    print(f"Credentials written to: {args.output_csv}")


if __name__ == "__main__":
    main()
