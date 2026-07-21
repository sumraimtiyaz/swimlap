"""Test doubles + a wiring helper.

These fakes satisfy the same Protocols as the production infra, which is exactly
why the service tests need no bcrypt, no JWT library, no FastAPI, and no database.
"""
from __future__ import annotations

import random
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.domain.errors import DomainError, ErrorCode
from app.domain.tuning import TUNING
from app.repositories.memory.repositories import (
    InMemoryAssignmentRepository,
    InMemoryLapRepository,
    InMemoryReferenceLapRepository,
    InMemorySwimRepository,
    InMemorySwimmerRepository,
    InMemoryUserRepository,
    InMemoryVenueRepository,
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


class MutableClock:
    """A clock the test drives by hand."""

    def __init__(self, start: datetime | None = None):
        self._t = start or datetime(2026, 7, 21, 9, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._t

    def now_ms(self) -> float:
        return self._t.timestamp() * 1000.0

    def advance(self, seconds: float) -> None:
        self._t += timedelta(seconds=seconds)

    def advance_ms(self, ms: float) -> None:
        self._t += timedelta(milliseconds=ms)

    def set(self, dt: datetime) -> None:
        self._t = dt


class PlainHasher:
    """NOT for production. Deterministic and dependency-free."""

    def hash(self, plain: str) -> str:
        return f"plain${plain}"

    def verify(self, plain: str, hashed: str) -> bool:
        return hashed == f"plain${plain}"


class FakeTokenProvider:
    def issue(self, *, subject: str, role: str) -> str:
        return f"token:{subject}:{role}"

    def decode(self, token: str) -> dict:
        try:
            _, subject, role = token.split(":")
        except ValueError as exc:  # pragma: no cover - defensive
            raise DomainError(ErrorCode.AUTH_TOKEN_EXPIRED, "Malformed token.") from exc
        return {"sub": subject, "role": role}


class Bundle:
    """A fully wired in-memory backend for integration-style service tests."""

    def __init__(self, *, failure_rate: float = 0.0, rng_seed: int = 1234) -> None:
        self.clock = MutableClock()
        self.users = InMemoryUserRepository()
        self.venues = InMemoryVenueRepository()
        self.swimmers = InMemorySwimmerRepository()
        self.swims = InMemorySwimRepository()
        self.assignments = InMemoryAssignmentRepository()
        self.laps = InMemoryLapRepository()
        self.references = InMemoryReferenceLapRepository()

        self.throttle = LoginThrottle(
            max_attempts=TUNING.auth.max_failed_attempts,
            lockout_minutes=TUNING.auth.lockout_minutes,
            clock=self.clock,
        )
        self.auth = AuthService(self.users, PlainHasher(), FakeTokenProvider(), self.throttle)
        self.user_admin = UserAdminService(self.users, PlainHasher(), self.clock)
        self.swim_service = SwimService(
            self.swims, self.assignments, self.laps, self.users, self.venues, self.swimmers,
            self.clock, TUNING.swim,
        )
        ref_tuning = replace(TUNING.reference, failure_rate=failure_rate)
        self.reference = ReferenceService(self.references, ref_tuning, random.Random(rng_seed))
        self.lap_ingest = LapIngestService(
            self.swims, self.assignments, self.laps, self.clock, TUNING.lap_ingest,
            self.swim_service, reference_service=self.reference,
        )
        self.report = ReportService(self.swims, self.laps, self.references, self.swimmers, self.venues)
        self.presence = PresenceService(self.clock)
        self.live = LiveViewService(
            self.swims, self.laps, self.assignments, self.users, self.swimmers, self.venues,
            self.presence, self.clock,
        )
