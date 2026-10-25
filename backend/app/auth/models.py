from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

ExperimentArm = Literal["generic", "static_personalized", "closed_loop"]

ALL_ARMS: tuple[ExperimentArm, ...] = ("generic", "static_personalized", "closed_loop")


class UserRegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, description="Minimum 6 characters")
    display_name: str = Field(min_length=1, max_length=100)


class UserLoginIn(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str
    arm: ExperimentArm
    consent_at: datetime | None = None
    created_at: datetime


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class ConsentResponse(BaseModel):
    consent_at: datetime


class UserRecord(BaseModel):
    id: UUID
    email: str
    password_hash: str
    display_name: str
    created_at: datetime
    consent_at: datetime | None = None
    deleted_at: datetime | None = None


class ExperimentAssignment(BaseModel):
    user_id: UUID
    arm: ExperimentArm
    assigned_at: datetime
