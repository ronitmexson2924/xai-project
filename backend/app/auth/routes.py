from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.deps import get_current_user
from app.auth.models import (
    AuthResponse,
    ConsentResponse,
    UserLoginIn,
    UserRegisterIn,
    UserResponse,
)
from app.auth.security import create_access_token, hash_password, verify_password
from app.auth.store import UserAlreadyExistsError, auth_store

router = APIRouter(tags=["auth"])


@router.post(
    "/auth/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new learner account",
)
def register(payload: UserRegisterIn) -> AuthResponse:
    try:
        pw_hash = hash_password(payload.password)
        user, assignment = auth_store.register_user(
            email=payload.email,
            password_hash=pw_hash,
            display_name=payload.display_name,
        )
    except UserAlreadyExistsError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "USER_ALREADY_EXISTS",
                    "message": "Email is already registered",
                }
            },
        ) from err

    token = create_access_token(user.id)
    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        arm=assignment.arm,
        consent_at=user.consent_at,
        created_at=user.created_at,
    )
    return AuthResponse(token=token, user=user_resp)


@router.post(
    "/auth/login",
    response_model=AuthResponse,
    summary="Log in with email and password",
)
def login(payload: UserLoginIn) -> AuthResponse:
    user = auth_store.get_user_by_email(payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "Incorrect email or password",
                }
            },
        )

    assignment = auth_store.get_assignment(user.id)
    arm = assignment.arm if assignment else "generic"

    token = create_access_token(user.id)
    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        arm=arm,
        consent_at=user.consent_at,
        created_at=user.created_at,
    )
    return AuthResponse(token=token, user=user_resp)


@router.post(
    "/auth/consent",
    response_model=ConsentResponse,
    summary="Record learner informed consent",
)
def consent(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> ConsentResponse:
    consent_at = auth_store.set_consent(current_user.id)
    return ConsentResponse(consent_at=consent_at)


@router.get(
    "/auth/me",
    response_model=UserResponse,
    summary="Get current user details",
)
@router.get(
    "/me",
    response_model=UserResponse,
    include_in_schema=False,
)
def get_me(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> UserResponse:
    return current_user


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete current user account",
)
def delete_me(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> Response:
    auth_store.soft_delete_user(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
