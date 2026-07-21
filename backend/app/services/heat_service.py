"""Heat orchestration service.

Owns the heat lifecycle: creating a heat (and its per-lane timers), taking it
live, and closing it. All state changes go through the pure state machine so an
illegal transition is impossible regardless of caller.
"""
from __future__ import annotations

from datetime import datetime

from app.domain import state_machine as sm
from app.domain.entities import Assignment, Heat, Timer
from app.domain.enums import ClosureMethod, HeatState, TimerState, UserRole
from app.domain.errors import DomainError, ErrorCode
from app.domain.tuning import HeatTuning
from app.repositories.interfaces import (
    AssignmentRepository,
    HeatRepository,
    LapRepository,
    TimerRepository,
    UserRepository,
)
from app.services.ports import Clock


class HeatService:
    def __init__(
        self,
        heats: HeatRepository,
        timers: TimerRepository,
        assignments: AssignmentRepository,
        laps: LapRepository,
        users: UserRepository,
        clock: Clock,
        tuning: HeatTuning,
    ):
        self._heats = heats
        self._timers = timers
        self._assignments = assignments
        self._laps = laps
        self._users = users
        self._clock = clock
        self._tuning = tuning

    # -- creation -----------------------------------------------------------
    def create_heat(self, *, name: str, scheduled_start: datetime, lane_count: int, target_laps: int) -> Heat:
        if not (1 <= lane_count <= self._tuning.max_lane_count):
            raise DomainError(ErrorCode.VALIDATION_ERROR, f"lane_count must be 1..{self._tuning.max_lane_count}.")
        if target_laps < 1:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "target_laps must be >= 1.")

        heat = self._heats.add(Heat(
            id=0, name=name.strip(), scheduled_start=scheduled_start,
            state=HeatState.SCHEDULED, lane_count=lane_count, target_laps=target_laps,
        ))
        # Materialize one timer per lane up front so assignment and live view have
        # something stable to reference.
        for lane in range(1, lane_count + 1):
            self._timers.add(Timer(id=0, heat_id=heat.id, lane=lane, assigned_user_id=None))
        return heat

    def assign_timekeeper(self, *, heat_id: int, user_id: int, lane: int) -> Assignment:
        heat = self._require_heat(heat_id)
        if heat.state is HeatState.CLOSED:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "Cannot assign to a closed heat.")

        user = self._users.get_by_id(user_id)
        if user is None:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "User not found.")
        if user.role is not UserRole.TIMEKEEPER:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "Only timekeepers can be assigned to lanes.")

        timer = next((t for t in self._timers.list_for_heat(heat_id) if t.lane == lane), None)
        if timer is None:
            raise DomainError(ErrorCode.VALIDATION_ERROR, f"Lane {lane} does not exist on this heat.")

        timer.assigned_user_id = user_id
        self._timers.update(timer)
        return self._assignments.add(Assignment(id=0, heat_id=heat_id, user_id=user_id, lane=lane))

    # -- lifecycle ----------------------------------------------------------
    def start_heat(self, heat_id: int) -> Heat:
        heat = self._require_heat(heat_id)
        sm.assert_transition(heat.state, HeatState.LIVE)
        heat.state = HeatState.LIVE
        heat.went_live_ts_ms = self._clock.now_ms()
        return self._heats.update(heat)

    def close_heat(self, heat_id: int, *, method: ClosureMethod | None = None) -> Heat:
        heat = self._require_heat(heat_id)
        sm.assert_transition(heat.state, HeatState.CLOSED)

        all_done = self._all_timers_completed(heat_id)
        resolved = method or sm.closure_method_for(all_timers_completed=all_done, triggered_by_inactivity=False)

        heat.state = HeatState.CLOSED
        heat.closure_method = resolved
        heat.closed_ts_ms = self._clock.now_ms()
        return self._heats.update(heat)

    def auto_close_if_inactive(self, heat_id: int) -> Heat | None:
        """Called by the inactivity monitor. Returns the heat if it was closed."""
        heat = self._heats.get(heat_id)
        if heat is None or heat.state is not HeatState.LIVE:
            return None

        laps = self._laps.list_for_heat(heat_id)
        last_activity = max((l.server_ts_ms for l in laps), default=heat.went_live_ts_ms)
        should_close = sm.should_auto_close_for_inactivity(
            last_activity_server_ts_ms=last_activity,
            now_server_ts_ms=self._clock.now_ms(),
            timeout_seconds=self._tuning.auto_inactivity_timeout_seconds,
        )
        if not should_close:
            return None
        return self.close_heat(heat_id, method=ClosureMethod.AUTO_INACTIVITY)

    # -- queries ------------------------------------------------------------
    def heats_for_timekeeper(self, user_id: int) -> list[Heat]:
        heat_ids = {a.heat_id for a in self._assignments.list_for_user(user_id)}
        return [h for h in (self._heats.get(hid) for hid in heat_ids) if h is not None]

    # -- helpers ------------------------------------------------------------
    def _require_heat(self, heat_id: int) -> Heat:
        heat = self._heats.get(heat_id)
        if heat is None:
            raise DomainError(ErrorCode.HEAT_NOT_FOUND, "Heat does not exist.")
        return heat

    def _all_timers_completed(self, heat_id: int) -> bool:
        timers = self._timers.list_for_heat(heat_id)
        assigned = [t for t in timers if t.assigned_user_id is not None]
        if not assigned:
            return False
        return all(t.state is TimerState.COMPLETED for t in assigned)
