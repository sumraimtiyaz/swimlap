"""Presence — is this timer's app connected right now?

PRD §7.2: presence answers exactly one question and is **never written to the
database**. It is derived state; stored as fact it goes stale (after a restart a
persisted ``active`` row would keep claiming a timer is connected when nothing
is). The app pings every ~10s; no ping for 30s reads as offline. A single
instance is shared across requests (wired as a singleton in ``deps``).
"""
from __future__ import annotations

from datetime import datetime

from app.services.ports import Clock

OFFLINE_AFTER_SECONDS = 30


class PresenceService:
    def __init__(self, clock: Clock):
        self._clock = clock
        self._last_ping: dict[int, datetime] = {}  # timer_id -> last ping time

    def ping(self, timer_id: int) -> None:
        self._last_ping[timer_id] = self._clock.now()

    def last_ping(self, timer_id: int) -> datetime | None:
        return self._last_ping.get(timer_id)

    def is_connected(self, timer_id: int) -> bool:
        ts = self._last_ping.get(timer_id)
        if ts is None:
            return False
        return (self._clock.now() - ts).total_seconds() <= OFFLINE_AFTER_SECONDS
