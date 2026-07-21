"""Authentication routes."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ServicesDep
from app.api.presenters import user_out
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, services: ServicesDep) -> LoginResponse:
    result = services.auth.login(body.username, body.password)
    return LoginResponse(token=result.token, user=user_out(result.user))
