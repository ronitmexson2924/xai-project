"""Prepare a local database in one step: content, demo learners and an admin.

    python -m app.devstack ../content      (from backend/; `docker compose up` runs it on start)

Safe to run on every start: content is upserted, and the demo learners and the admin are created
only when they do not exist yet, so a restart keeps what you did in the app. Local development and
demos only: it refuses to run with ENVIRONMENT=production.
"""

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.onboard import create_admin
from app.auth.security import hash_password
from app.auth.store import normalise_email
from app.db import models as m
from app.graph.content import load_content
from app.graph.demo_seed import DEMO_DOMAIN, build
from app.graph.seed import seed

DEFAULT_DEMO_PASSWORD = "Demo-pass-1"
DEFAULT_ADMIN_EMAIL = "admin@example.com"
DEFAULT_ADMIN_PASSWORD = "Admin-pass-1"


def prepare(
    session: Session,
    content_dir: Path,
    demo_password: str = DEFAULT_DEMO_PASSWORD,
    admin_email: str = DEFAULT_ADMIN_EMAIL,
    admin_password: str = DEFAULT_ADMIN_PASSWORD,
) -> list[str]:
    """Load content and create whatever is missing. Returns what was done, for the log."""
    counts = seed(session, load_content(content_dir))
    done = [f"content: {counts['concepts']} concepts, {counts['items']} questions"]

    demo_users = (
        select(func.count()).select_from(m.User).where(m.User.email.like(f"%{DEMO_DOMAIN}"))
    )
    if session.scalar(demo_users):
        done.append("demo learners: already there")
    else:
        build(session, hash_password(demo_password))
        done.append(f"demo learners: asha|ben|chen{DEMO_DOMAIN} (password {demo_password})")

    admin_email = normalise_email(admin_email)
    if session.scalar(select(m.User.id).where(m.User.email == admin_email)) is None:
        create_admin(session, admin_email, admin_password, "Local admin")
        done.append(f"admin: {admin_email} (password {admin_password})")
    else:
        done.append(f"admin: {admin_email} already there")
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("content_dir", type=Path)
    args = parser.parse_args(argv)

    from app.config import settings
    from app.db.session import SessionLocal

    if settings.environment == "production":
        print("refusing to create demo accounts with ENVIRONMENT=production", file=sys.stderr)
        return 1
    with SessionLocal() as session:
        done = prepare(
            session,
            args.content_dir,
            demo_password=os.environ.get("DEMO_PASSWORD", DEFAULT_DEMO_PASSWORD),
            admin_email=os.environ.get("ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL),
            admin_password=os.environ.get("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD),
        )
        session.commit()
    for line in done:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
