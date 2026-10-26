from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt

from app.config import settings

ALGORITHM = "HS256"
BCRYPT_MAX_BYTES = 72  # bcrypt ignores (or rejects) anything longer; the API enforces this

# A real bcrypt hash of a random string: verifying against it when an email is unknown takes as
# long as a real check, so response time does not reveal which emails are registered.
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str | None) -> bool:
    """Constant-work check: an unknown user or an unusable hash still costs one bcrypt round."""
    candidate = password.encode("utf-8")[:BCRYPT_MAX_BYTES]
    target = hashed_password if hashed_password and hashed_password.startswith("$2") else None
    try:
        ok = bcrypt.checkpw(candidate, (target or _DUMMY_HASH).encode("utf-8"))
    except ValueError:
        return False
    return ok and target is not None


def _secret() -> str:
    return settings.jwt_secret


def create_access_token(user_id: UUID, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(hours=settings.jwt_expire_hours))
    # sub-second iat, so a token issued just after a logout is told apart from one just before
    payload = {"sub": str(user_id), "iat": now.timestamp(), "exp": int(expire.timestamp())}
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> tuple[UUID, datetime] | None:
    """(user id, issued at) for a valid, unexpired token signed with our secret; else None."""
    try:
        payload = jwt.decode(
            token, _secret(), algorithms=[ALGORITHM], options={"require": ["sub", "exp", "iat"]}
        )
        return UUID(payload["sub"]), datetime.fromtimestamp(payload["iat"], UTC)
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        return None
