"""Report service — assembles the on-request report for one swim.

Pulls the raw captures + references and runs the pure ``build_report``. Adds the
display context (swimmer, venue, lane, status) the console/report screen needs.
Nothing is stored; the report reflects everything received so far, live or closed.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities import Swim
from app.domain.errors import DomainError, ErrorCode
from app.domain.report import SwimReport, build_report
from app.repositories.interfaces import (
    LapRepository,
    ReferenceLapRepository,
    SwimmerRepository,
    SwimRepository,
    VenueRepository,
)


@dataclass(frozen=True)
class ReportContext:
    swim: Swim
    swimmer_name: str
    venue_name: str
    report: SwimReport


class ReportService:
    def __init__(
        self,
        swims: SwimRepository,
        laps: LapRepository,
        references: ReferenceLapRepository,
        swimmers: SwimmerRepository,
        venues: VenueRepository,
    ):
        self._swims = swims
        self._laps = laps
        self._refs = references
        self._swimmers = swimmers
        self._venues = venues

    def build(self, swim_id: int) -> ReportContext:
        swim = self._swims.get(swim_id)
        if swim is None:
            raise DomainError(ErrorCode.SWIM_NOT_FOUND, "Swim does not exist.")
        report = build_report(
            scheduled_start=swim.scheduled_start,
            laps=self._laps.list_for_swim(swim_id),
            references=self._refs.list_for_swim(swim_id),
            simulated=True,
        )
        swimmer = self._swimmers.get(swim.swimmer_id)
        venue = self._venues.get(swim.venue_id)
        return ReportContext(
            swim=swim,
            swimmer_name=swimmer.name if swimmer else "",
            venue_name=venue.name if venue else "",
            report=report,
        )
