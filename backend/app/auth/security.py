from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt

from app.config import settings

ALGORITHM = "HS256"
DEFAULT_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def _get_jwt_secret() -> str:
    secret = settings.jwt_secret
    if len(secret) < 32:
        return secret.ljust(32, "-")
    return secret


def create_access_token(user_id: UUID, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(UTC)
    delta = expires_delta if expires_delta is not None else timedelta(days=DEFAULT_EXPIRE_DAYS)
    expire = now + delta
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> UUID | None:
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            return None
        return UUID(sub)
    except Exception:
        return None
