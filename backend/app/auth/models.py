from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.auth.security import BCRYPT_MAX_BYTES

ExperimentArm = Literal["generic", "static_personalized", "closed_loop"]

ALL_ARMS: tuple[ExperimentArm, ...] = ("generic", "static_personalized", "closed_loop")

MIN_PASSWORD_LENGTH = 8


class UserRegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=BCRYPT_MAX_BYTES)
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
            raise ValueError(f"password must be at most {BCRYPT_MAX_BYTES} bytes")
        if "\x00" in value:
            raise ValueError("password must not contain NUL characters")
        if value.strip() == "" or len(set(value)) < 4:
            raise ValueError("password is too simple")
        return value

    @field_validator("display_name")
    @classmethod
    def display_name_is_plain_text(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("display name must not be blank")
        if any(not ch.isprintable() for ch in value):
            raise ValueError("display name contains control characters")
        return value


class UserLoginIn(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str
    arm: ExperimentArm
    consent_at: datetime | None = None
    created_at: datetime
    is_admin: bool = False


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class ConsentResponse(BaseModel):
    consent_at: datetime
