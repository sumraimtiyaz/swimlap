"""Coordinator-only routes: accounts, setup, assignment, live view, report, closing.

Every route is guarded by ``RequireCoordinator``. Route order matters: the literal
``/swims/live`` is declared before ``/swims/{swim_id}`` so it is matched first.
"""
from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.deps import Repositories, RequireCoordinator, ServicesDep
from app.api.presenters import (
    issued_account_out,
    live_row_out,
    report_out,
    swim_detail_out,
    swim_out,
    swimmer_out,
    user_out,
    venue_out,
)
from app.domain.enums import ClosureMethod, UserRole
from app.domain.errors import DomainError, ErrorCode
from app.schemas.auth import UserOut
from app.schemas.live import LiveRowOut
from app.schemas.report import ReportOut
from app.schemas.swim import AssignRequest, CreateSwimRequest, SwimDetailOut, SwimOut
from app.schemas.swimmer import CreateSwimmerRequest, SwimmerOut
from app.schemas.user import CreateUserRequest, IssuedAccountOut
from app.schemas.venue import CreateVenueRequest, VenueOut
from app.services.simulator import SimulatorService

router = APIRouter(tags=["coordinator"])


# -- helpers ----------------------------------------------------------------
def _swim_detail(repos: Repositories, swim_id: int) -> SwimDetailOut:
    swim = repos.swims.get(swim_id)
    if swim is None:
        raise DomainError(ErrorCode.SWIM_NOT_FOUND, "Swim does not exist.")
    swimmer = repos.swimmers.get(swim.swimmer_id)
    venue = repos.venues.get(swim.venue_id)
    assignment = repos.assignments.get_for_swim(swim_id)
    timer = repos.users.get_by_id(assignment.timer_id) if assignment else None
    return swim_detail_out(
        swim, swimmer_name=swimmer.name if swimmer else "",
        venue_name=venue.name if venue else "",
        assignment=assignment, timer_name=timer.display_name if timer else None,
    )


# -- accounts ---------------------------------------------------------------
@router.post("/users", response_model=IssuedAccountOut, status_code=201)
def create_user(body: CreateUserRequest, services: ServicesDep, _: RequireCoordinator) -> IssuedAccountOut:
    issued = services.users.create_user(username=body.username, display_name=body.display_name, role=body.role)
    return issued_account_out(issued)


@router.get("/users", response_model=list[UserOut])
def list_users(services: ServicesDep, _: RequireCoordinator, role: UserRole | None = None) -> list[UserOut]:
    return [user_out(u) for u in services.users.list_users(role)]


@router.post("/users/{user_id}/reset-password", response_model=IssuedAccountOut)
def reset_password(user_id: int, services: ServicesDep, _: RequireCoordinator) -> IssuedAccountOut:
    return issued_account_out(services.users.reset_password(user_id))


@router.patch("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, services: ServicesDep, _: RequireCoordinator) -> UserOut:
    return user_out(services.users.deactivate(user_id))


# -- venues / swimmers ------------------------------------------------------
@router.post("/venues", response_model=VenueOut, status_code=201)
def create_venue(body: CreateVenueRequest, services: ServicesDep, _: RequireCoordinator) -> VenueOut:
    from app.domain.entities import Venue
    venue = services.repos.venues.add(Venue(id=0, name=body.name.strip(), lane_count=body.lane_count))
    return venue_out(venue)


@router.get("/venues", response_model=list[VenueOut])
def list_venues(services: ServicesDep, _: RequireCoordinator) -> list[VenueOut]:
    return [venue_out(v) for v in services.repos.venues.list_all()]


@router.post("/swimmers", response_model=SwimmerOut, status_code=201)
def create_swimmer(body: CreateSwimmerRequest, services: ServicesDep, _: RequireCoordinator) -> SwimmerOut:
    from app.domain.entities import Swimmer
    swimmer = services.repos.swimmers.add(Swimmer(id=0, name=body.name.strip()))
    return swimmer_out(swimmer)


@router.get("/swimmers", response_model=list[SwimmerOut])
def list_swimmers(services: ServicesDep, _: RequireCoordinator) -> list[SwimmerOut]:
    return [swimmer_out(s) for s in services.repos.swimmers.list_all()]


# -- swims ------------------------------------------------------------------
@router.post("/swims", response_model=SwimDetailOut, status_code=201)
def create_swim(body: CreateSwimRequest, services: ServicesDep, _: RequireCoordinator) -> SwimDetailOut:
    swim = services.swims.create_swim(
        venue_id=body.venue_id, swimmer_id=body.swimmer_id, lane_no=body.lane_no,
        scheduled_start=body.scheduled_start, lap_target=body.lap_target)
    return _swim_detail(services.repos, swim.id)


@router.get("/swims", response_model=list[SwimOut])
def list_swims(services: ServicesDep, _: RequireCoordinator) -> list[SwimOut]:
    out: list[SwimOut] = []
    for swim in services.repos.swims.list_all():
        swimmer = services.repos.swimmers.get(swim.swimmer_id)
        venue = services.repos.venues.get(swim.venue_id)
        out.append(swim_out(swim, swimmer_name=swimmer.name if swimmer else "",
                            venue_name=venue.name if venue else ""))
    return out


@router.get("/swims/live", response_model=list[LiveRowOut])
def live_swims(services: ServicesDep, _: RequireCoordinator) -> list[LiveRowOut]:
    return [live_row_out(r) for r in services.live_view.live_rows()]


@router.get("/swims/{swim_id}", response_model=SwimDetailOut)
def get_swim(swim_id: int, services: ServicesDep, _: RequireCoordinator) -> SwimDetailOut:
    return _swim_detail(services.repos, swim_id)


@router.get("/swims/{swim_id}/report", response_model=ReportOut)
def swim_report(swim_id: int, services: ServicesDep, _: RequireCoordinator) -> ReportOut:
    return report_out(services.report.build(swim_id))


@router.post("/swims/{swim_id}/close", response_model=SwimOut)
def close_swim(swim_id: int, services: ServicesDep, _: RequireCoordinator) -> SwimOut:
    return swim_out(services.swims.close_swim(swim_id, method=ClosureMethod.COORDINATOR))


@router.post("/swims/{swim_id}/simulate")
def simulate(swim_id: int, services: ServicesDep, _: RequireCoordinator,
             laps: int = 8, interval_ms: float = 40_000.0) -> dict:
    sim = SimulatorService(services.lap_ingest, services.repos.swims, services.repos.assignments, services.repos.laps)
    summary = sim.simulate_swim(swim_id, laps=laps, interval_ms=interval_ms)
    return {"laps_submitted": summary.laps_submitted}


# -- assignments ------------------------------------------------------------
@router.post("/assignments", status_code=201)
def assign(body: AssignRequest, services: ServicesDep, _: RequireCoordinator) -> dict:
    assignment = services.swims.assign_timer(swim_id=body.swim_id, timer_id=body.timer_id)
    return {"id": assignment.id, "swim_id": assignment.swim_id, "timer_id": assignment.timer_id}


@router.delete("/assignments/{assignment_id}", status_code=204)
def unassign(assignment_id: int, services: ServicesDep, _: RequireCoordinator) -> Response:
    services.swims.unassign(assignment_id)
    return Response(status_code=204)
