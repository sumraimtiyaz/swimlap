"""Swim orchestration service.

Owns the swim lifecycle: creating a swim, assigning its one timer, taking it live
(on the first capture — done from the lap path), and closing it. All state
changes go through the pure state machine so an illegal transition is impossible
regardless of caller.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.domain import state_machine as sm
from app.domain.entities import Assignment, Swim
from app.domain.enums import ClosureMethod, SwimStatus, UserRole
from app.domain.errors import DomainError, ErrorCode
from app.domain.tuning import SwimTuning
from app.repositories.interfaces import (
    AssignmentRepository,
    LapRepository,
    SwimRepository,
    SwimmerRepository,
    UserRepository,
    VenueRepository,
)
from app.services.ports import Clock

# Heuristic swim duration used only for overlap detection (PRD §8.2). We have no
# real end time, so we estimate one from the lap target.
_NOMINAL_LAP_SECONDS = 45
_DEFAULT_LAPS_FOR_WINDOW = 20


class SwimService:
    def __init__(
        self,
        swims: SwimRepository,
        assignments: AssignmentRepository,
        laps: LapRepository,
        users: UserRepository,
        venues: VenueRepository,
        swimmers: SwimmerRepository,
        clock: Clock,
        tuning: SwimTuning,
    ):
        self._swims = swims
        self._assignments = assignments
        self._laps = laps
        self._users = users
        self._venues = venues
        self._swimmers = swimmers
        self._clock = clock
        self._tuning = tuning

    # -- creation -----------------------------------------------------------
    def create_swim(self, *, venue_id: int, swimmer_id: int, lane_no: int,
                    scheduled_start: datetime, lap_target: int | None) -> Swim:
        venue = self._venues.get(venue_id)
        if venue is None:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "Venue not found.")
        if self._swimmers.get(swimmer_id) is None:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "Swimmer not found.")
        if not (1 <= lane_no <= venue.lane_count):
            raise DomainError(ErrorCode.VALIDATION_ERROR, f"lane_no must be 1..{venue.lane_count}.")
        if lap_target is not None and lap_target < 1:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "lap_target must be >= 1 when set.")

        return self._swims.add(Swim(
            id=0, venue_id=venue_id, swimmer_id=swimmer_id, lane_no=lane_no,
            scheduled_start=scheduled_start, lap_target=lap_target, status=SwimStatus.SCHEDULED,
        ))

    def assign_timer(self, *, swim_id: int, timer_id: int) -> Assignment:
        swim = self._require(swim_id)
        if swim.status is SwimStatus.CLOSED:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "Cannot assign a timer to a closed swim.")

        user = self._users.get_by_id(timer_id)
        if user is None:
            raise DomainError(ErrorCode.USER_NOT_FOUND, "User not found.")
        if user.role is not UserRole.TIMER:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "Only timers can be assigned to a swim.")

        existing = self._assignments.get_for_swim(swim_id)
        if existing is not None:
            if existing.timer_id == timer_id:
                return existing  # idempotent
            raise DomainError(ErrorCode.VALIDATION_ERROR, "This swim already has a timer assigned.")

        # PRD §8.2: a timer cannot hold two swims whose scheduled windows overlap.
        for a in self._assignments.list_for_timer(timer_id):
            other = self._swims.get(a.swim_id)
            if other is not None and other.id != swim_id and self._overlaps(swim, other):
                raise DomainError(
                    ErrorCode.OVERLAPPING_ASSIGNMENT,
                    "This timer is already assigned to a swim at an overlapping time.",
                    {"conflicting_swim_id": other.id},
                )

        return self._assignments.add(Assignment(id=0, swim_id=swim_id, timer_id=timer_id))

    def unassign(self, assignment_id: int) -> None:
        self._assignments.delete(assignment_id)

    # -- lifecycle ----------------------------------------------------------
    def take_live(self, swim: Swim) -> Swim:
        """First capture takes a scheduled swim live; the origin (scheduled_start)
        never changes. Idempotent for an already-live swim."""
        if swim.status is not SwimStatus.SCHEDULED:
            return swim
        sm.assert_transition(swim.status, SwimStatus.LIVE)
        swim.status = SwimStatus.LIVE
        return self._swims.update(swim)

    def close_swim(self, swim_id: int, *, method: ClosureMethod) -> Swim:
        swim = self._require(swim_id)
        sm.assert_transition(swim.status, SwimStatus.CLOSED)
        swim.status = SwimStatus.CLOSED
        swim.closure_method = method
        swim.closed_at = self._clock.now()
        return self._swims.update(swim)

    def auto_close_if_inactive(self, swim_id: int) -> Swim | None:
        """Called by the inactivity monitor. Returns the swim if it was closed."""
        swim = self._swims.get(swim_id)
        if swim is None or swim.status is not SwimStatus.LIVE:
            return None
        laps = self._laps.list_for_swim(swim_id)
        last_activity = max((l.server_ts for l in laps), default=None)
        if sm.should_auto_close_for_inactivity(
            last_activity=last_activity, now=self._clock.now(),
            timeout_seconds=self._tuning.auto_inactivity_timeout_seconds,
        ):
            return self.close_swim(swim_id, method=ClosureMethod.AUTO_INACTIVITY)
        return None

    # -- queries ------------------------------------------------------------
    def swims_for_timer(self, timer_id: int, *, statuses: tuple[SwimStatus, ...] | None = None) -> list[Swim]:
        ids = {a.swim_id for a in self._assignments.list_for_timer(timer_id)}
        swims = [s for s in (self._swims.get(i) for i in ids) if s is not None]
        if statuses is not None:
            swims = [s for s in swims if s.status in statuses]
        return sorted(swims, key=lambda s: s.scheduled_start)

    # -- helpers ------------------------------------------------------------
    def _require(self, swim_id: int) -> Swim:
        swim = self._swims.get(swim_id)
        if swim is None:
            raise DomainError(ErrorCode.SWIM_NOT_FOUND, "Swim does not exist.")
        return swim

    def _overlaps(self, a: Swim, b: Swim) -> bool:
        return (a.scheduled_start < b.scheduled_start + self._window(b)
                and b.scheduled_start < a.scheduled_start + self._window(a))

    def _window(self, swim: Swim) -> timedelta:
        laps = swim.lap_target or _DEFAULT_LAPS_FOR_WINDOW
        return timedelta(seconds=laps * _NOMINAL_LAP_SECONDS)
