import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterOrganization(BaseModel):
    organization_name: str = Field(min_length=2, max_length=120)
    organization_slug: str = Field(
        min_length=2, max_length=64, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    admin_email: EmailStr
    admin_password: str = Field(min_length=12, max_length=128)


class RegistrationResult(BaseModel):
    organization_id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str = Field(max_length=256)


class SessionTokenResponse(TokenResponse):
    refresh_token: str
    session_expires_at: datetime
