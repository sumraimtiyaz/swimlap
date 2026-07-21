"""Timer-facing routes: assigned swims, resume, capture, completion, liveness.

Every route is guarded by ``RequireTimer`` *and* an ownership check — a valid
token is permission to touch *your* swim, not any swim (PRD §4).
"""
from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.deps import RequireTimer, ServicesDep
from app.api.presenters import ingest_result_out, swim_detail_out, swim_out
from app.core.clock import SystemClock
from app.domain.entities import User
from app.domain.enums import ClosureMethod, SwimStatus
from app.domain.errors import DomainError, ErrorCode
from app.domain.report import build_report
from app.schemas.lap import SubmitLapsRequest, SubmitLapsResponse
from app.schemas.swim import StateOut, SwimDetailOut, SwimOut
from app.services.lap_service import LapInput

router = APIRouter(tags=["timer"])

# Used only to stamp the arrival instant as the first act of the capture handler.
_clock = SystemClock()


def _require_owned_swim(services: ServicesDep, swim_id: int, user: User):
    swim = services.repos.swims.get(swim_id)
    if swim is None:
        raise DomainError(ErrorCode.SWIM_NOT_FOUND, "Swim does not exist.")
    assignment = services.repos.assignments.get_for_swim(swim_id)
    if assignment is None or assignment.timer_id != user.id:
        raise DomainError(ErrorCode.NOT_ASSIGNED, "You are not assigned to this swim.")
    return swim, assignment


@router.get("/my-swims", response_model=list[SwimDetailOut])
def my_swims(services: ServicesDep, user: RequireTimer) -> list[SwimDetailOut]:
    # Server-side filter to scheduled/live only — a closed swim is never returned.
    swims = services.swims.swims_for_timer(user.id, statuses=(SwimStatus.SCHEDULED, SwimStatus.LIVE))
    out: list[SwimDetailOut] = []
    for swim in swims:
        swimmer = services.repos.swimmers.get(swim.swimmer_id)
        venue = services.repos.venues.get(swim.venue_id)
        assignment = services.repos.assignments.get_for_swim(swim.id)
        out.append(swim_detail_out(
            swim, swimmer_name=swimmer.name if swimmer else "",
            venue_name=venue.name if venue else "",
            assignment=assignment, timer_name=user.display_name,
        ))
    return out


@router.get("/swims/{swim_id}/state", response_model=StateOut)
def swim_state(swim_id: int, services: ServicesDep, user: RequireTimer) -> StateOut:
    swim, _ = _require_owned_swim(services, swim_id, user)
    laps = services.repos.laps.list_for_swim(swim_id)
    valid_count = sum(1 for l in laps if l.is_valid)
    last_seq = services.repos.laps.highest_seq_for_swim(swim_id) or 0
    report = build_report(scheduled_start=swim.scheduled_start, laps=laps, references=[])
    recent = [rl.recorded_ms for rl in report.laps if rl.recorded_ms is not None][-3:]
    recent.reverse()  # most recent first
    return StateOut(swim_id=swim_id, status=swim.status, lap_count=valid_count,
                    last_seq=last_seq, recent_laps_ms=recent)


@router.post("/swims/{swim_id}/laps", response_model=SubmitLapsResponse)
def submit_laps(swim_id: int, body: SubmitLapsRequest, services: ServicesDep, user: RequireTimer) -> SubmitLapsResponse:
    # PRD §2/§7.1: stamp arrival as the first operation of the capture path.
    arrival = _clock.now()
    result = services.lap_ingest.ingest(
        swim_id=swim_id, timer_id=user.id,
        laps=[LapInput(seq=l.seq, device_mono_ms=l.device_mono_ms, device_ts=l.device_ts,
                       was_buffered=l.was_buffered, source=l.source.value) for l in body.laps],
        server_ts=arrival,
    )
    return ingest_result_out(result)


@router.post("/swims/{swim_id}/complete", response_model=SwimOut)
def complete_swim(swim_id: int, services: ServicesDep, user: RequireTimer) -> SwimOut:
    _require_owned_swim(services, swim_id, user)
    return swim_out(services.swims.close_swim(swim_id, method=ClosureMethod.TIMER_COMPLETED))


@router.post("/swims/{swim_id}/liveness", status_code=204)
def liveness(swim_id: int, services: ServicesDep, user: RequireTimer) -> Response:
    _require_owned_swim(services, swim_id, user)
    services.presence.ping(user.id)
    return Response(status_code=204)
