from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ExperimentArm = Literal["generic", "static_personalized", "closed_loop"]

ALL_ARMS: tuple[ExperimentArm, ...] = ("generic", "static_personalized", "closed_loop")

PASSWORD_MIN = 8
PASSWORD_MAX_BYTES = 72  # bcrypt ignores everything after 72 bytes


def _clean_name(value: str) -> str:
    value = " ".join(value.split())  # collapse whitespace, drop newlines and tabs
    if not value:
        raise ValueError("display name must not be blank")
    if any(not ch.isprintable() for ch in value):
        raise ValueError("display name contains control characters")
    return value


class UserRegisterIn(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=PASSWORD_MIN, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v.encode()) > PASSWORD_MAX_BYTES:
            raise ValueError(f"password must be at most {PASSWORD_MAX_BYTES} bytes")
        if v.strip() != v or not v.strip():
            raise ValueError("password must not start or end with spaces")
        return v

    @field_validator("display_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _clean_name(v)


class UserLoginIn(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str
    arm: ExperimentArm
    consent_at: datetime | None = None
    created_at: datetime
    is_admin: bool = False
    questionnaire_done: bool = False


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class ConsentResponse(BaseModel):
    consent_at: datetime
