"""Domain entities.

Plain dataclasses with no ORM/pydantic dependency. Services speak *these*;
repositories translate between these and whatever persistence exists
(SQLAlchemy, in-memory, ...). That boundary is what lets the whole service layer
be unit-tested without a database (Dependency Inversion).

The model follows the PRD: a **swim** is one swimmer, in one lane, watched by one
**timer** (a user with the ``timer`` role), for N laps. There is no per-lane
stopwatch entity — the timer *is* the assigned user.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .enums import ClosureMethod, LapSource, SwimStatus, UserRole


@dataclass
class User:
    id: int
    username: str
    display_name: str
    role: UserRole
    hashed_password: str
    is_active: bool = True
    created_at: datetime | None = None
    # Any token issued before this instant is rejected. Bumped on password reset
    # or deactivation so those actions kill every live token immediately (PRD §4).
    tokens_valid_from: datetime | None = None


@dataclass
class Venue:
    id: int
    name: str
    lane_count: int


@dataclass
class Swimmer:
    id: int
    name: str


@dataclass
class Swim:
    id: int
    venue_id: int
    swimmer_id: int
    lane_no: int
    scheduled_start: datetime
    lap_target: int | None
    status: SwimStatus
    closed_at: datetime | None = None
    closure_method: ClosureMethod | None = None


@dataclass
class Assignment:
    id: int
    swim_id: int
    timer_id: int  # the assigned user's id (role = timer)


@dataclass
class Lap:
    id: int
    swim_id: int
    timer_id: int
    seq: int
    device_mono_ms: float          # monotonic device reading — measures elapsed time reliably
    server_ts: datetime            # stamped on arrival; the only clock that counts (PRD §2)
    device_ts: datetime | None = None
    was_buffered: bool = False     # captured offline, synced later (client-flagged)
    was_late: bool = False         # arrived after the swim closed
    is_valid: bool = True          # timing values finite/plausible (audit; scoring filters this)
    source: LapSource = LapSource.MANUAL
    reasons: tuple[str, ...] = field(default_factory=tuple)
    created_at: datetime | None = None


@dataclass
class ReferenceLap:
    """The comparison timing for one lap (simulated today; swappable for real
    hardware later). Generated for lap n when lap n arrives."""

    id: int
    swim_id: int
    lap_no: int
    elapsed_ms: int
    is_valid: bool
    source: str  # 'simulated'
