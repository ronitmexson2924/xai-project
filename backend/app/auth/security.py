from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt

from app.config import settings

ALGORITHM = "HS256"
# compared against when the email is unknown, so a failed login takes as long either way
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str | None) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), (hashed_password or _DUMMY_HASH).encode())
    except ValueError:  # malformed hash, e.g. the placeholder of a demo or deleted account
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH.encode())
        return False


def create_access_token(user_id: UUID, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(hours=settings.jwt_expire_hours))
    payload = {"sub": str(user_id), "iat": int(now.timestamp()), "exp": int(expire.timestamp())}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> tuple[UUID, datetime] | None:
    """(user id, issued at) of a valid token, else None. Only HS256 is accepted, so a token
    signed with "none" or another algorithm is rejected."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
        return UUID(payload["sub"]), datetime.fromtimestamp(payload["iat"], UTC)
    except (jwt.PyJWTError, ValueError, TypeError):
        return None
