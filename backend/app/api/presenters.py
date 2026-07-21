"""Entity/result -> DTO mapping, shared by the route modules."""
from __future__ import annotations

from app.domain.entities import Assignment, Swim, Swimmer, User, Venue
from app.services.lap_service import IngestResult
from app.services.live_view_service import LiveRow
from app.services.report_service import ReportContext
from app.services.user_admin_service import IssuedAccount
from app.schemas.auth import UserOut
from app.schemas.lap import LapOutcomeOut, SubmitLapsResponse
from app.schemas.live import LiveRowOut
from app.schemas.report import ReportLapOut, ReportOut, ReportSummaryOut
from app.schemas.swim import SwimDetailOut, SwimOut
from app.schemas.swimmer import SwimmerOut
from app.schemas.user import IssuedAccountOut
from app.schemas.venue import VenueOut

SIMULATED_BANNER = "SIMULATED DATA — NOT MEASURED TIMING"


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.username, display_name=user.display_name,
                   role=user.role, is_active=user.is_active, created_at=user.created_at)


def issued_account_out(issued: IssuedAccount) -> IssuedAccountOut:
    return IssuedAccountOut(user=user_out(issued.user), password=issued.password)


def venue_out(venue: Venue) -> VenueOut:
    return VenueOut(id=venue.id, name=venue.name, lane_count=venue.lane_count)


def swimmer_out(swimmer: Swimmer) -> SwimmerOut:
    return SwimmerOut(id=swimmer.id, name=swimmer.name)


def swim_out(swim: Swim, *, swimmer_name: str = "", venue_name: str = "") -> SwimOut:
    return SwimOut(
        id=swim.id, venue_id=swim.venue_id, swimmer_id=swim.swimmer_id, lane_no=swim.lane_no,
        scheduled_start=swim.scheduled_start, lap_target=swim.lap_target, status=swim.status,
        closure_method=swim.closure_method, closed_at=swim.closed_at,
        swimmer_name=swimmer_name, venue_name=venue_name,
    )


def swim_detail_out(
    swim: Swim, *, swimmer_name: str = "", venue_name: str = "",
    assignment: Assignment | None = None, timer_name: str | None = None,
) -> SwimDetailOut:
    base = swim_out(swim, swimmer_name=swimmer_name, venue_name=venue_name).model_dump()
    return SwimDetailOut(
        **base,
        assigned_timer_id=assignment.timer_id if assignment else None,
        assigned_timer_name=timer_name,
        assignment_id=assignment.id if assignment else None,
    )


def ingest_result_out(result: IngestResult) -> SubmitLapsResponse:
    return SubmitLapsResponse(
        outcomes=[
            LapOutcomeOut(seq=o.seq, status=o.status, is_valid=o.is_valid, was_late=o.was_late,
                          was_buffered=o.was_buffered, reasons=list(o.reasons))
            for o in result.outcomes
        ],
        valid_lap_count=result.valid_lap_count,
        swim_status=result.swim_status,
        went_live=result.went_live,
    )


def report_out(ctx: ReportContext) -> ReportOut:
    r = ctx.report
    return ReportOut(
        swim_id=ctx.swim.id, swimmer_name=ctx.swimmer_name, venue_name=ctx.venue_name,
        lane_no=ctx.swim.lane_no, status=ctx.swim.status, scheduled_start=ctx.swim.scheduled_start,
        simulated=r.simulated, banner=SIMULATED_BANNER if r.simulated else "",
        laps=[
            ReportLapOut(
                lap_no=l.lap_no, seq=l.seq, recorded_ms=l.recorded_ms, cumulative_ms=l.cumulative_ms,
                reference_ms=l.reference_ms, deviation_ms=l.deviation_ms, derived=l.derived,
                was_late=l.was_late, is_valid=l.is_valid, note=l.note,
            )
            for l in r.laps
        ],
        summary=ReportSummaryOut(
            laps_recorded=r.summary.laps_recorded,
            average_deviation_ms=r.summary.average_deviation_ms,
            largest_deviation_ms=r.summary.largest_deviation_ms,
            largest_deviation_lap=r.summary.largest_deviation_lap,
            laps_without_comparison=r.summary.laps_without_comparison,
            late_count=r.summary.late_count,
            comparable=r.summary.comparable,
        ),
    )


def live_row_out(row: LiveRow) -> LiveRowOut:
    return LiveRowOut(
        swim_id=row.swim_id, swimmer_name=row.swimmer_name, venue_name=row.venue_name,
        lane_no=row.lane_no, timer_id=row.timer_id, timer_name=row.timer_name,
        connected=row.connected, lap_count=row.lap_count, last_lap_ms=row.last_lap_ms,
        stalled=row.stalled,
    )
