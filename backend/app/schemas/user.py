"""User management DTOs (coordinator only)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import UserRole
from app.schemas.auth import UserOut


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120, description="Login id handed to the timer")
    display_name: str = Field(min_length=1, max_length=120)
    # No password field: the system generates it (PRD §4).
    role: UserRole = UserRole.TIMER


class IssuedAccountOut(BaseModel):
    """Returned once on create/reset — carries the one-time plaintext password."""

    user: UserOut
    password: str
