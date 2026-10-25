from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import accounts
from app.auth.db import DbSession
from app.auth.models import UserResponse
from app.auth.security import decode_access_token

security = HTTPBearer(auto_error=False)


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": code, "message": message}},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    session: DbSession,
) -> UserResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("UNAUTHORIZED", "Missing bearer token")
    decoded = decode_access_token(credentials.credentials)
    if decoded is None:
        raise _unauthorized("UNAUTHORIZED", "Invalid or expired token")
    user_id, issued_at = decoded
    user = accounts.active_user(session, user_id)
    if user is None:
        raise _unauthorized("UNAUTHORIZED", "Invalid or expired token")
    return accounts.to_response(session, user)


CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


def require_consent(user: CurrentUser) -> UserResponse:
    if user.consent_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "CONSENT_REQUIRED",
                    "message": "Informed consent is required before accessing learning routes.",
                }
            },
        )
    return user


def require_admin(user: CurrentUser) -> UserResponse:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Administrator access required"}},
        )
    return user


ConsentedUser = Annotated[UserResponse, Depends(require_consent)]
AdminUser = Annotated[UserResponse, Depends(require_admin)]
