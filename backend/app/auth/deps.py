from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import UserResponse
from app.auth.security import decode_access_token
from app.auth.store import auth_store

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> UserResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Missing bearer token"}},
        )

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid or expired token"}},
        )

    user = auth_store.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found or deleted"}},
        )

    assignment = auth_store.get_assignment(user.id)
    arm = assignment.arm if assignment else "generic"

    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        arm=arm,
        consent_at=user.consent_at,
        created_at=user.created_at,
    )


def require_consent(
    user: Annotated[UserResponse, Depends(get_current_user)],
) -> UserResponse:
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
