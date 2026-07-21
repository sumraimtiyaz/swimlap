"""The report (pure).

Answers one question: **how far was each recorded lap from its reference?**
Computed on request from the raw captures + references; nothing is stored.

Rules (PRD §10):
- Lap 1 is measured from the scheduled start, marked *derived*, and excluded from
  the average (the push-off was never captured).
- Every other lap is the gap between consecutive captures — from ``server_ts``,
  unless the capture was buffered, in which case from ``device_mono_ms`` (§2).
- ``deviation = recorded − reference`` where a *valid* reference exists.
- Every capture appears, including odd/late ones. Late captures are shown but
  excluded from the average, with their count stated.
- No number ever renders as ``NaN``/``Infinity`` or a misleading zero — such a
  cell is simply blank (``None``).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .entities import Lap, ReferenceLap
from .numeric import is_finite_number


@dataclass(frozen=True)
class ReportLap:
    lap_no: int                     # display index, 1-based
    seq: int
    recorded_ms: float | None
    cumulative_ms: float | None
    reference_ms: int | None
    deviation_ms: float | None
    derived: bool
    was_late: bool
    is_valid: bool
    note: str


@dataclass(frozen=True)
class ReportSummary:
    laps_recorded: int
    average_deviation_ms: float | None
    largest_deviation_ms: float | None
    largest_deviation_lap: int | None
    laps_without_comparison: int
    late_count: int
    comparable: bool


@dataclass(frozen=True)
class SwimReport:
    laps: list[ReportLap]
    summary: ReportSummary
    simulated: bool


def _ms_between(a: datetime, b: datetime) -> float | None:
    delta = (a - b).total_seconds() * 1000.0
    return delta if is_finite_number(delta) else None


def build_report(
    *,
    scheduled_start: datetime,
    laps: list[Lap],
    references: list[ReferenceLap],
    simulated: bool = True,
) -> SwimReport:
    """Build the full report. ``laps`` may be in any order; references are matched
    to a lap by ``lap_no == lap.seq`` (a reference is generated per lap on arrival)."""
    ordered = sorted(laps, key=lambda l: l.seq)
    ref_by_lapno = {r.lap_no: r for r in references}

    report_laps: list[ReportLap] = []
    running_total: float = 0.0

    for i, lap in enumerate(ordered):
        derived = i == 0

        # -- recorded lap time -------------------------------------------------
        if derived:
            recorded = _ms_between(lap.server_ts, scheduled_start)
        else:
            prev = ordered[i - 1]
            if lap.was_buffered:
                # A whole offline queue arrives in one instant, so server_ts is
                # meaningless here — measure elapsed time from the monotonic clock.
                d = lap.device_mono_ms - prev.device_mono_ms
                recorded = d if is_finite_number(d) else None
            else:
                recorded = _ms_between(lap.server_ts, prev.server_ts)

        # -- cumulative --------------------------------------------------------
        if recorded is not None:
            running_total += recorded
            cumulative: float | None = running_total
        else:
            cumulative = None

        # -- reference + deviation --------------------------------------------
        ref = ref_by_lapno.get(lap.seq)
        reference_ms = ref.elapsed_ms if (ref is not None and ref.is_valid) else None

        if derived or reference_ms is None or recorded is None:
            deviation: float | None = None
        else:
            deviation = recorded - reference_ms

        report_laps.append(ReportLap(
            lap_no=i + 1, seq=lap.seq, recorded_ms=recorded, cumulative_ms=cumulative,
            reference_ms=reference_ms, deviation_ms=deviation, derived=derived,
            was_late=lap.was_late, is_valid=lap.is_valid,
            note=_note(derived=derived, is_valid=lap.is_valid, was_late=lap.was_late,
                       has_reference=reference_ms is not None, reasons=lap.reasons),
        ))

    summary = _summarise(report_laps)
    return SwimReport(laps=report_laps, summary=summary, simulated=simulated)


def _note(*, derived: bool, is_valid: bool, was_late: bool, has_reference: bool, reasons: tuple[str, ...]) -> str:
    if derived:
        return "derived from scheduled start"
    if not is_valid:
        return "flagged: " + (", ".join(reasons) if reasons else "invalid")
    if was_late:
        return "late — excluded from average"
    if not has_reference:
        return "no reference"
    return ""


def _summarise(laps: list[ReportLap]) -> ReportSummary:
    # The average is over laps that genuinely have a comparison: a valid lap, not
    # derived, not late, with a valid reference and a finite deviation.
    comparable = [
        l for l in laps
        if l.deviation_ms is not None and not l.derived and not l.was_late and l.is_valid
    ]
    late_count = sum(1 for l in laps if l.was_late)
    without_comparison = sum(1 for l in laps if l.deviation_ms is None)

    if comparable:
        average = sum(l.deviation_ms for l in comparable) / len(comparable)  # type: ignore[misc]
        largest = max(comparable, key=lambda l: abs(l.deviation_ms))  # type: ignore[arg-type]
        largest_ms: float | None = largest.deviation_ms
        largest_lap: int | None = largest.lap_no
    else:
        average = None
        largest_ms = None
        largest_lap = None

    return ReportSummary(
        laps_recorded=len(laps),
        average_deviation_ms=average,
        largest_deviation_ms=largest_ms,
        largest_deviation_lap=largest_lap,
        laps_without_comparison=without_comparison,
        late_count=late_count,
        comparable=bool(comparable),
    )
