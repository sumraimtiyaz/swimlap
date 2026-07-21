"""Auth DTOs."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import UserRole


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: UserRole
    is_active: bool = True
    created_at: datetime | None = None


class LoginResponse(BaseModel):
    token: str
    user: UserOut
