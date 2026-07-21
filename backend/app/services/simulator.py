"""Simulated tap generator (demo/QA only).

Drives the *real* ingest path (same validation, reconciliation, idempotency,
reference generation) rather than writing rows directly, so a simulated swim
exercises exactly the production code — invaluable for demos without a phone on
the deck. Taps are spaced in server time so live lap deltas look realistic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.domain.enums import LapSource, SwimStatus
from app.domain.errors import DomainError, ErrorCode
from app.repositories.interfaces import AssignmentRepository, LapRepository, SwimRepository
from app.services.lap_service import LapIngestService, LapInput


@dataclass
class SimulationSummary:
    laps_submitted: int


class SimulatorService:
    def __init__(
        self,
        lap_ingest: LapIngestService,
        swims: SwimRepository,
        assignments: AssignmentRepository,
        laps: LapRepository,
    ):
        self._ingest = lap_ingest
        self._swims = swims
        self._assignments = assignments
        self._laps = laps

    def simulate_swim(self, swim_id: int, *, laps: int = 8, interval_ms: float = 40_000.0) -> SimulationSummary:
        swim = self._swims.get(swim_id)
        if swim is None:
            raise DomainError(ErrorCode.SWIM_NOT_FOUND, "Swim does not exist.")
        if swim.status is SwimStatus.CLOSED:
            raise DomainError(ErrorCode.SWIM_NOT_LIVE, "Cannot simulate a closed swim.")
        assignment = self._assignments.get_for_swim(swim_id)
        if assignment is None:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "Assign a timer before simulating.")

        start_seq = (self._laps.highest_seq_for_swim(swim_id) or 0) + 1
        base_mono = 10_000.0
        submitted = 0
        for i in range(laps):
            seq = start_seq + i
            # Space arrivals in server time from the scheduled start so lap 1 reads
            # as one interval and subsequent live deltas are realistic.
            arrival = swim.scheduled_start + timedelta(milliseconds=interval_ms * (i + 1))
            self._ingest.ingest(
                swim_id=swim_id, timer_id=assignment.timer_id,
                laps=[LapInput(seq=seq, device_mono_ms=base_mono + interval_ms * (i + 1),
                               source=LapSource.MANUAL.value)],
                server_ts=arrival,
            )
            submitted += 1
        return SimulationSummary(laps_submitted=submitted)
