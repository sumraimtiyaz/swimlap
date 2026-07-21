"""Composition root.

FastAPI's dependency system is our IoC container. ``build_services`` is the
single spot that decides which repository adapter to instantiate based on
``settings.persistence`` — the Open/Closed seam. Everything downstream depends on
Protocols and never learns whether it is talking to Postgres or a dict.

Process-lifetime state that must survive across requests but is *not* persisted —
presence and the login throttle (both derived, per PRD §4/§7.2) — lives in
module-level singletons here.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.clock import SystemClock
from app.core.config import Settings, get_settings
from app.core.security import BcryptPasswordHasher, JwtTokenProvider
from app.db.session import get_session
from app.domain.entities import User
from app.domain.enums import UserRole
from app.domain.errors import DomainError, ErrorCode
from app.domain.tuning import TUNING
from app.repositories.interfaces import (
    AssignmentRepository,
    LapRepository,
    ReferenceLapRepository,
    SwimRepository,
    SwimmerRepository,
    UserRepository,
    VenueRepository,
)
from app.services.auth_service import AuthService
from app.services.lap_service import LapIngestService
from app.services.live_view_service import LiveViewService
from app.services.login_throttle import LoginThrottle
from app.services.presence_service import PresenceService
from app.services.reference_service import ReferenceService
from app.services.report_service import ReportService
from app.services.swim_service import SwimService
from app.services.user_admin_service import UserAdminService


@dataclass
class Repositories:
    users: UserRepository
    venues: VenueRepository
    swimmers: SwimmerRepository
    swims: SwimRepository
    assignments: AssignmentRepository
    laps: LapRepository
    references: ReferenceLapRepository


@dataclass
class Services:
    repos: Repositories
    auth: AuthService
    users: UserAdminService
    swims: SwimService
    lap_ingest: LapIngestService
    reference: ReferenceService
    report: ReportService
    live_view: LiveViewService
    presence: PresenceService


# Stateless singletons — safe to share across requests.
_clock = SystemClock()
_hasher = BcryptPasswordHasher()
_rng = random.Random()
# Derived, process-lifetime state (never persisted) — must be shared.
_presence = PresenceService(_clock)
_throttle = LoginThrottle(
    max_attempts=TUNING.auth.max_failed_attempts,
    lockout_minutes=TUNING.auth.lockout_minutes,
    clock=_clock,
)


def _token_provider(settings: Settings) -> JwtTokenProvider:
    return JwtTokenProvider(
        secret=settings.jwt_secret, algorithm=settings.jwt_algorithm, ttl_minutes=settings.jwt_ttl_minutes)


def build_repositories(session: Session | None, settings: Settings) -> Repositories:
    if settings.persistence == "memory":
        from app.repositories.memory.repositories import (
            InMemoryAssignmentRepository, InMemoryLapRepository, InMemoryReferenceLapRepository,
            InMemorySwimRepository, InMemorySwimmerRepository, InMemoryUserRepository,
            InMemoryVenueRepository,
        )
        return Repositories(
            users=InMemoryUserRepository(), venues=InMemoryVenueRepository(),
            swimmers=InMemorySwimmerRepository(), swims=InMemorySwimRepository(),
            assignments=InMemoryAssignmentRepository(), laps=InMemoryLapRepository(),
            references=InMemoryReferenceLapRepository(),
        )

    assert session is not None, "SQLAlchemy persistence requires a session"
    from app.repositories.sqlalchemy.repositories import (
        SqlAssignmentRepository, SqlLapRepository, SqlReferenceLapRepository, SqlSwimRepository,
        SqlSwimmerRepository, SqlUserRepository, SqlVenueRepository,
    )
    return Repositories(
        users=SqlUserRepository(session), venues=SqlVenueRepository(session),
        swimmers=SqlSwimmerRepository(session), swims=SqlSwimRepository(session),
        assignments=SqlAssignmentRepository(session), laps=SqlLapRepository(session),
        references=SqlReferenceLapRepository(session),
    )


def build_services(repos: Repositories, settings: Settings) -> Services:
    tokens = _token_provider(settings)
    auth = AuthService(repos.users, _hasher, tokens, _throttle)
    users = UserAdminService(repos.users, _hasher, _clock)
    swim = SwimService(repos.swims, repos.assignments, repos.laps, repos.users,
                       repos.venues, repos.swimmers, _clock, TUNING.swim)
    reference = ReferenceService(repos.references, TUNING.reference, _rng)
    lap_ingest = LapIngestService(repos.swims, repos.assignments, repos.laps, _clock,
                                  TUNING.lap_ingest, swim, reference_service=reference)
    report = ReportService(repos.swims, repos.laps, repos.references, repos.swimmers, repos.venues)
    live_view = LiveViewService(repos.swims, repos.laps, repos.assignments, repos.users,
                                repos.swimmers, repos.venues, _presence, _clock)
    return Services(repos=repos, auth=auth, users=users, swims=swim, lap_ingest=lap_ingest,
                    reference=reference, report=report, live_view=live_view, presence=_presence)


def get_services(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session | None, Depends(get_session)] = None,  # type: ignore[assignment]
) -> Services:
    if settings.persistence == "memory":
        repos: Repositories = request.app.state.memory_repos
    else:
        repos = build_repositories(session, settings)
    return build_services(repos, settings)


ServicesDep = Annotated[Services, Depends(get_services)]

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
    services: ServicesDep,
) -> User:
    if creds is None or not creds.credentials:
        raise DomainError(ErrorCode.AUTH_TOKEN_EXPIRED, "Missing bearer token.")
    payload = _token_provider(settings).decode(creds.credentials)
    user = services.repos.users.get_by_id(int(payload["sub"]))
    if user is None:
        raise DomainError(ErrorCode.AUTH_TOKEN_EXPIRED, "User no longer exists.")
    if not user.is_active:
        raise DomainError(ErrorCode.AUTH_ACCOUNT_DISABLED, "This account has been deactivated.")
    # Token revocation: a reset/deactivate bumps tokens_valid_from, killing any
    # token issued earlier (PRD §4) — no server-side session store needed.
    if user.tokens_valid_from is not None:
        iat = payload.get("iat")
        issued_at = datetime.fromtimestamp(iat, tz=timezone.utc) if iat is not None else None
        if issued_at is None or issued_at < user.tokens_valid_from:
            raise DomainError(ErrorCode.AUTH_TOKEN_EXPIRED, "Session is no longer valid; sign in again.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed: UserRole):
    def _guard(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise DomainError(ErrorCode.FORBIDDEN_ROLE, "Your role may not perform this action.")
        return user

    return _guard


RequireCoordinator = Annotated[User, Depends(require_role(UserRole.COORDINATOR))]
RequireTimer = Annotated[User, Depends(require_role(UserRole.TIMER))]
