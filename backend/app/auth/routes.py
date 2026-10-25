from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.middleware import limit_auth_attempts
from app.auth import accounts
from app.auth.db import DbSession
from app.auth.deps import CurrentUser
from app.auth.models import (
    AuthResponse,
    ConsentResponse,
    UserLoginIn,
    UserRegisterIn,
    UserResponse,
)
from app.auth.security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])


@router.post(
    "/auth/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new learner account",
)
def register(payload: UserRegisterIn, request: Request, session: DbSession) -> AuthResponse:
    limit_auth_attempts(request, payload.email)
    try:
        user = accounts.register(
            session, payload.email, hash_password(payload.password), payload.display_name
        )
    except accounts.UserAlreadyExistsError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {"code": "USER_ALREADY_EXISTS", "message": "Email is already registered"}
            },
        ) from err
    session.commit()
    return AuthResponse(
        token=create_access_token(user.id), user=accounts.to_response(session, user)
    )


@router.post("/auth/login", response_model=AuthResponse, summary="Log in with email and password")
def login(payload: UserLoginIn, request: Request, session: DbSession) -> AuthResponse:
    limit_auth_attempts(request, payload.email)
    user = accounts.by_email(session, payload.email)
    # always run bcrypt, so the response time does not reveal whether the email exists
    ok = verify_password(payload.password, user.password_hash if user else None)
    if user is None or not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "INVALID_CREDENTIALS", "message": "Incorrect email or password"}
            },
        )
    return AuthResponse(
        token=create_access_token(user.id), user=accounts.to_response(session, user)
    )


@router.post("/auth/consent", response_model=ConsentResponse, summary="Record informed consent")
def consent(current_user: CurrentUser, session: DbSession) -> ConsentResponse:
    user = accounts.active_user(session, current_user.id)
    assert user is not None  # get_current_user checked it in this session
    consent_at = accounts.give_consent(session, user)
    session.commit()
    return ConsentResponse(consent_at=consent_at)


@router.get("/auth/me", response_model=UserResponse, summary="Get current user details")
@router.get("/me", response_model=UserResponse, include_in_schema=False)
def get_me(current_user: CurrentUser) -> UserResponse:
    return current_user


@router.delete(
    "/me", status_code=status.HTTP_204_NO_CONTENT, summary="Delete the current user's account"
)
def delete_me(current_user: CurrentUser, session: DbSession) -> Response:
    user = accounts.active_user(session, current_user.id)
    assert user is not None
    accounts.delete_account(session, user)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
