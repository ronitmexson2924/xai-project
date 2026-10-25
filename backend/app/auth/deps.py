from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.models import ExperimentArm, UserResponse
from app.auth.security import decode_access_token
from app.auth.store import get_active_user
from app.db import models as m
from app.db.session import get_db

security = HTTPBearer(auto_error=False)

DbDep = Annotated[Session, Depends(get_db)]


def _error(code: int, error: str, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"error": {"code": error, "message": message}})


@dataclass
class CurrentUser:
    """The authenticated account for this request (the ORM row plus its arm)."""

    row: m.User
    arm: ExperimentArm

    @property
    def id(self) -> UUID:
        return self.row.id

    @property
    def is_admin(self) -> bool:
        return self.row.is_admin

    def response(self) -> UserResponse:
        return UserResponse(
            id=self.row.id,
            email=self.row.email,
            display_name=self.row.display_name,
            arm=self.arm,
            consent_at=self.row.consent_at,
            created_at=self.row.created_at,
            is_admin=self.row.is_admin,
        )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    session: DbDep,
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Missing bearer token")
    decoded = decode_access_token(credentials.credentials)
    if decoded is None:
        raise _error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Invalid or expired token")
    user_id, issued_at = decoded
    found = get_active_user(session, user_id)
    if found is None:
        raise _error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Invalid or expired token")
    user, arm = found
    if user.tokens_valid_after is not None and issued_at < user.tokens_valid_after:
        raise _error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Invalid or expired token")
    return CurrentUser(row=user, arm=arm)


def require_consent(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if user.row.consent_at is None:
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "CONSENT_REQUIRED",
            "Informed consent is required before accessing learning routes.",
        )
    return user


def require_admin(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if not user.is_admin:
        raise _error(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Administrator access required")
    return user


UserDep = Annotated[CurrentUser, Depends(get_current_user)]
LearnerDep = Annotated[CurrentUser, Depends(require_consent)]
AdminDep = Annotated[CurrentUser, Depends(require_admin)]
