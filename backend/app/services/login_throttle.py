"""In-memory login throttle.

PRD §4: *five failed attempts on one login id block further attempts for fifteen
minutes.* This is derived, short-lived state — a process-local counter, like
presence — so it lives in memory and is intentionally never persisted. After a
server restart everyone starts clean, which is acceptable (and fail-open on
availability, not on credentials).

A single instance is shared across requests (wired as a singleton in ``deps``).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.domain.errors import DomainError, ErrorCode
from app.services.ports import Clock


class LoginThrottle:
    def __init__(self, *, max_attempts: int, lockout_minutes: int, clock: Clock):
        self._max = max_attempts
        self._lockout = timedelta(minutes=lockout_minutes)
        self._clock = clock
        self._state: dict[str, tuple[int, datetime | None]] = {}  # username -> (fails, locked_until)

    def check(self, username: str) -> None:
        """Raise ``AUTH_LOCKED`` if this login id is currently blocked."""
        _, until = self._state.get(username, (0, None))
        now = self._clock.now()
        if until is not None and now < until:
            retry = int((until - now).total_seconds())
            raise DomainError(
                ErrorCode.AUTH_LOCKED,
                "Too many failed attempts. Try again later.",
                {"retry_after_seconds": retry},
            )

    def record_failure(self, username: str) -> None:
        fails, until = self._state.get(username, (0, None))
        now = self._clock.now()
        if until is not None and now >= until:  # previous lock expired — start fresh
            fails, until = 0, None
        fails += 1
        if fails >= self._max:
            until = now + self._lockout
        self._state[username] = (fails, until)

    def record_success(self, username: str) -> None:
        self._state.pop(username, None)
