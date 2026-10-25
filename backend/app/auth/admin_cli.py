"""Grant or revoke the admin role (there is deliberately no HTTP route for this).

python -m app.auth.admin_cli grant someone@example.com
python -m app.auth.admin_cli revoke someone@example.com
"""

import argparse
import sys

from app.auth import accounts
from app.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["grant", "revoke"])
    parser.add_argument("email")
    args = parser.parse_args()
    with SessionLocal() as session:
        user = accounts.by_email(session, args.email.strip().lower())
        if user is None:
            sys.exit(f"no active account for {args.email}")
        user.is_admin = args.action == "grant"
        session.commit()
    print(f"{args.email}: admin={args.action == 'grant'}")


if __name__ == "__main__":
    main()
