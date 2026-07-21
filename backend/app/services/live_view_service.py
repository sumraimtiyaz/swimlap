"""Coordinator live view assembly (PRD §8.3).

One row per live swim. **Connected** (presence) and **capturing** (lap count
moving) are different signals and both are surfaced. A *stalled* warning fires
when the lap count has not moved for longer than twice the typical lap time in
that swim — showing tapping has stopped, long before auto-closure would.

Reuses ``build_report`` for the recorded-lap-time maths (server_ts vs buffered
mono deltas) so the live view and the report never disagree.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.report import build_report
from app.repositories.interfaces import (
    AssignmentRepository,
    LapRepository,
    SwimmerRepository,
    SwimRepository,
    UserRepository,
    VenueRepository,
)
from app.services.ports import Clock
from app.services.presence_service import PresenceService


@dataclass(frozen=True)
class LiveRow:
    swim_id: int
    swimmer_name: str
    venue_name: str
    lane_no: int
    timer_id: int | None
    timer_name: str | None
    connected: bool
    lap_count: int
    last_lap_ms: float | None
    stalled: bool


class LiveViewService:
    def __init__(
        self,
        swims: SwimRepository,
        laps: LapRepository,
        assignments: AssignmentRepository,
        users: UserRepository,
        swimmers: SwimmerRepository,
        venues: VenueRepository,
        presence: PresenceService,
        clock: Clock,
    ):
        self._swims = swims
        self._laps = laps
        self._assignments = assignments
        self._users = users
        self._swimmers = swimmers
        self._venues = venues
        self._presence = presence
        self._clock = clock

    def live_rows(self) -> list[LiveRow]:
        from app.domain.enums import SwimStatus
        rows: list[LiveRow] = []
        now = self._clock.now()
        for swim in self._swims.list_by_status(SwimStatus.LIVE):
            assignment = self._assignments.get_for_swim(swim.id)
            timer = self._users.get_by_id(assignment.timer_id) if assignment else None
            swimmer = self._swimmers.get(swim.swimmer_id)
            venue = self._venues.get(swim.venue_id)

            laps = self._laps.list_for_swim(swim.id)
            valid = [l for l in laps if l.is_valid]
            report = build_report(scheduled_start=swim.scheduled_start, laps=laps, references=[])
            recorded = [rl.recorded_ms for rl in report.laps if not rl.derived and rl.recorded_ms is not None]
            last_lap_ms = report.laps[-1].recorded_ms if report.laps else None

            connected = self._presence.is_connected(assignment.timer_id) if assignment else False
            stalled = self._is_stalled(laps=laps, typical_ms=(sum(recorded) / len(recorded)) if recorded else None, now=now)

            rows.append(LiveRow(
                swim_id=swim.id,
                swimmer_name=swimmer.name if swimmer else "",
                venue_name=venue.name if venue else "",
                lane_no=swim.lane_no,
                timer_id=assignment.timer_id if assignment else None,
                timer_name=timer.display_name if timer else None,
                connected=connected,
                lap_count=len(valid),
                last_lap_ms=last_lap_ms,
                stalled=stalled,
            ))
        return rows

    def _is_stalled(self, *, laps, typical_ms, now) -> bool:
        if typical_ms is None or typical_ms <= 0 or not laps:
            return False
        last_server_ts = max(l.server_ts for l in laps)
        idle_ms = (now - last_server_ts).total_seconds() * 1000.0
        return idle_ms > 2 * typical_ms
