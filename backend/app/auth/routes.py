from fastapi import APIRouter, HTTPException, Request, Response, status

from app.auth.deps import DbDep, UserDep
from app.auth.limits import client_ip, login_throttle, windows
from app.auth.models import AuthResponse, ConsentResponse, UserLoginIn, UserRegisterIn, UserResponse
from app.auth.security import create_access_token, hash_password, verify_password
from app.auth.store import (
    UserAlreadyExistsError,
    get_active_user,
    get_user_by_email,
    is_onboarded,
    normalise_email,
    register_user,
    revoke_tokens,
    set_consent,
    soft_delete_user,
)
from app.config import settings

router = APIRouter(tags=["auth"])


def _error(code: int, error: str, message: str, headers: dict[str, str] | None = None):
    return HTTPException(
        status_code=code, detail={"error": {"code": error, "message": message}}, headers=headers
    )


@router.post(
    "/auth/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new learner account",
)
def register(payload: UserRegisterIn, request: Request, session: DbDep) -> AuthResponse:
    if not settings.allow_registration:
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "REGISTRATION_CLOSED",
            "Sign-up is closed. Use the account you were given.",
        )
    # every attempt counts, taken or not, so the 409 below cannot be used to test emails in bulk
    if settings.rate_limit_enabled and (
        wait := windows.hit(f"register:{client_ip(request)}", settings.register_max_per_hour, 3600)
    ):
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "TOO_MANY_REGISTRATIONS",
            "Too many sign-ups from this network. Try again later.",
            headers={"Retry-After": str(wait)},
        )
    try:
        user, arm = register_user(
            session,
            email=payload.email,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name,
        )
    except UserAlreadyExistsError:
        raise _error(
            status.HTTP_409_CONFLICT, "USER_ALREADY_EXISTS", "Email is already registered"
        ) from None
    session.commit()
    token = create_access_token(user.id)
    found = get_active_user(session, user.id)
    assert found is not None
    return AuthResponse(token=token, user=_response(*found))


@router.post("/auth/login", response_model=AuthResponse, summary="Log in with email and password")
def login(payload: UserLoginIn, request: Request, session: DbDep) -> AuthResponse:
    keys = (f"email:{normalise_email(payload.email)}", f"ip:{client_ip(request)}")
    if wait := login_throttle.retry_after(*keys):
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "TOO_MANY_LOGIN_ATTEMPTS",
            "Too many failed logins. Try again later.",
            headers={"Retry-After": str(wait)},
        )
    user = get_user_by_email(session, payload.email)
    if not verify_password(payload.password, user.password_hash if user else None) or not user:
        login_throttle.failed(*keys)
        raise _error(
            status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS", "Incorrect email or password"
        )
    login_throttle.succeeded(keys[0])
    found = get_active_user(session, user.id)
    assert found is not None
    return AuthResponse(
        token=create_access_token(user.id),
        user=_response(*found, onboarded=is_onboarded(session, user.id)),
    )


@router.post("/auth/consent", response_model=ConsentResponse, summary="Record informed consent")
def consent(current: UserDep, session: DbDep) -> ConsentResponse:
    consent_at = set_consent(session, current.row)
    session.commit()
    return ConsentResponse(consent_at=consent_at)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out on every device (revokes all tokens issued so far)",
)
def logout(current: UserDep, session: DbDep) -> Response:
    revoke_tokens(session, current.row)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/me", response_model=UserResponse, summary="Get current user details")
@router.get("/me", response_model=UserResponse, include_in_schema=False)
def get_me(current: UserDep, session: DbDep) -> UserResponse:
    return current.response(onboarded=is_onboarded(session, current.id))


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Withdraw: deactivate the account now; its data is purged by the retention job",
)
def delete_me(current: UserDep, session: DbDep) -> Response:
    soft_delete_user(session, current.row)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _response(user, arm, onboarded: bool = False) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        arm=arm,
        consent_at=user.consent_at,
        created_at=user.created_at,
        is_admin=user.is_admin,
        onboarded=onboarded,
    )
