"""Lap ingestion — the busiest write path in the system.

Design goals, in priority order:

1. **Never lose a real tap.** Bad data is *flagged* (``is_valid=False``), not
   dropped, so a coordinator can audit it. Every status accepts a submission so
   buffered laps synced after closure still land.
2. **The server clock is the only clock that counts (PRD §2).** ``server_ts`` is
   stamped at arrival (captured by the route as its first act and passed in here)
   and is the basis for live lap times. Buffered laps — flagged by the client —
   are timed from ``device_mono_ms`` deltas instead, because a whole offline queue
   arrives in one instant.
3. **Idempotent.** Phones retry after flaky connectivity; the same
   ``(timer_id, swim_id, seq)`` submitted twice yields one row.

Depends only on repository Protocols + the pure domain, so the entire path is
unit-tested against in-memory fakes with no database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain import validation
from app.domain.entities import Lap
from app.domain.enums import LapSource, SwimStatus
from app.domain.errors import DomainError, ErrorCode
from app.domain.tuning import LapIngestTuning
from app.repositories.interfaces import AssignmentRepository, LapRepository, SwimRepository
from app.services.ports import Clock
from app.services.swim_service import SwimService


@dataclass(frozen=True)
class LapInput:
    seq: int
    device_mono_ms: float
    device_ts: datetime | None = None
    was_buffered: bool = False
    source: str = LapSource.MANUAL.value


@dataclass
class LapOutcome:
    seq: int
    status: str  # 'accepted' | 'duplicate' | 'invalid'
    is_valid: bool
    was_late: bool
    was_buffered: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class IngestResult:
    outcomes: list[LapOutcome]
    valid_lap_count: int
    swim_status: SwimStatus
    went_live: bool = False


class LapIngestService:
    def __init__(
        self,
        swims: SwimRepository,
        assignments: AssignmentRepository,
        laps: LapRepository,
        clock: Clock,
        tuning: LapIngestTuning,
        swim_service: SwimService,
        reference_service=None,  # optional: generates a reference per lap on arrival
    ):
        self._swims = swims
        self._assignments = assignments
        self._laps = laps
        self._clock = clock
        self._tuning = tuning
        self._swim_service = swim_service
        self._reference_service = reference_service

    def ingest(
        self,
        *,
        swim_id: int,
        timer_id: int,
        laps: list[LapInput],
        server_ts: datetime | None = None,
    ) -> IngestResult:
        if len(laps) > self._tuning.max_laps_per_batch:
            raise DomainError(ErrorCode.VALIDATION_ERROR, f"Batch exceeds {self._tuning.max_laps_per_batch} laps.")

        swim = self._swims.get(swim_id)
        if swim is None:
            raise DomainError(ErrorCode.SWIM_NOT_FOUND, "Swim does not exist.")

        # Ownership (PRD §4): a valid token is permission to touch *your* swim.
        assignment = self._assignments.get_for_swim(swim_id)
        if assignment is None or assignment.timer_id != timer_id:
            raise DomainError(ErrorCode.NOT_ASSIGNED, "You are not assigned to this swim.")

        # server_ts is stamped by the route the instant the request arrived; fall
        # back to now() only when called directly (tests, simulator).
        arrival = server_ts if server_ts is not None else self._clock.now()
        now = self._clock.now()

        outcomes: list[LapOutcome] = []
        # Process in seq order so validation context (previous seq/mono) is coherent
        # even when an offline buffer uploads unordered.
        for lap in sorted(laps, key=lambda l: l.seq):
            outcomes.append(self._ingest_one(swim, timer_id, lap, arrival, now))

        # The first (valid) capture takes a scheduled swim live; origin unchanged.
        went_live = False
        current = self._swims.get(swim_id)
        if current is not None and current.status is SwimStatus.SCHEDULED and any(o.is_valid for o in outcomes):
            current = self._swim_service.take_live(current)
            went_live = True

        valid_count = sum(1 for l in self._laps.list_for_swim(swim_id) if l.is_valid)
        return IngestResult(
            outcomes=outcomes,
            valid_lap_count=valid_count,
            swim_status=current.status if current else swim.status,
            went_live=went_live,
        )

    # -- per-lap ------------------------------------------------------------
    def _ingest_one(self, swim, timer_id: int, lap: LapInput, arrival: datetime, now: datetime) -> LapOutcome:
        # Idempotency: a seq we've already stored is returned as-is.
        existing = self._laps.get_by_timer_swim_seq(timer_id, swim.id, lap.seq)
        if existing is not None:
            return LapOutcome(
                seq=lap.seq, status="duplicate", is_valid=existing.is_valid,
                was_late=existing.was_late, was_buffered=existing.was_buffered, reasons=("duplicate_seq",),
            )

        last_valid = self._laps.last_valid_for_swim(swim.id)
        ctx = validation.LapContext(
            previous_seq=self._laps.highest_seq_for_swim(swim.id),
            previous_mono_ms=last_valid.device_mono_ms if last_valid else None,
        )
        verdict = validation.validate_lap(
            validation.LapCandidate(seq=lap.seq, device_mono_ms=lap.device_mono_ms, source=lap.source),
            ctx, self._tuning,
        )
        was_late = validation.is_late(arrival, swim.closed_at, self._tuning)
        source = lap.source if lap.source in {s.value for s in LapSource} else LapSource.MANUAL.value

        stored = self._laps.add(Lap(
            id=0, swim_id=swim.id, timer_id=timer_id, seq=lap.seq,
            device_mono_ms=lap.device_mono_ms, server_ts=arrival, device_ts=lap.device_ts,
            was_buffered=lap.was_buffered, was_late=was_late, is_valid=verdict.is_valid,
            source=LapSource(source), reasons=verdict.reasons, created_at=now,
        ))

        # PRD §9: generate the reference for lap n when lap n arrives.
        if stored.is_valid and self._reference_service is not None:
            self._reference_service.ensure_for_lap(swim.id, stored.seq)

        return LapOutcome(
            seq=stored.seq, status="accepted" if stored.is_valid else "invalid",
            is_valid=stored.is_valid, was_late=stored.was_late, was_buffered=stored.was_buffered,
            reasons=stored.reasons,
        )
