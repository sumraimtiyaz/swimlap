"""SQLAlchemy repository adapters.

Each class takes a live ``Session`` and implements the matching Protocol from
``repositories.interfaces``. Row<->entity translation lives in the private
``_to_*`` mappers so the domain never sees an ORM object. These satisfy the exact
same interface as the in-memory adapters, so services are identical in prod and
test.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.entities import Assignment, Lap, ReferenceLap, Swim, Swimmer, User, Venue
from app.domain.enums import ClosureMethod, LapSource, SwimStatus, UserRole
from app.models.assignment import AssignmentRow
from app.models.lap import LapRow
from app.models.reference_lap import ReferenceLapRow
from app.models.swim import SwimRow
from app.models.swimmer import SwimmerRow
from app.models.user import UserRow
from app.models.venue import VenueRow


# -- mappers ----------------------------------------------------------------
def _to_user(row: UserRow) -> User:
    return User(
        id=row.id, username=row.username, display_name=row.display_name,
        role=UserRole(row.role), hashed_password=row.hashed_password,
        is_active=row.is_active, created_at=row.created_at, tokens_valid_from=row.tokens_valid_from,
    )


def _to_venue(row: VenueRow) -> Venue:
    return Venue(id=row.id, name=row.name, lane_count=row.lane_count)


def _to_swimmer(row: SwimmerRow) -> Swimmer:
    return Swimmer(id=row.id, name=row.name)


def _to_swim(row: SwimRow) -> Swim:
    return Swim(
        id=row.id, venue_id=row.venue_id, swimmer_id=row.swimmer_id, lane_no=row.lane_no,
        scheduled_start=row.scheduled_start, lap_target=row.lap_target, status=SwimStatus(row.status),
        closed_at=row.closed_at,
        closure_method=ClosureMethod(row.closure_method) if row.closure_method else None,
    )


def _to_assignment(row: AssignmentRow) -> Assignment:
    return Assignment(id=row.id, swim_id=row.swim_id, timer_id=row.timer_id)


def _to_lap(row: LapRow) -> Lap:
    return Lap(
        id=row.id, swim_id=row.swim_id, timer_id=row.timer_id, seq=row.seq,
        device_mono_ms=row.device_mono_ms, server_ts=row.server_ts, device_ts=row.device_ts,
        was_buffered=row.was_buffered, was_late=row.was_late, is_valid=row.is_valid,
        source=LapSource(row.source),
        reasons=tuple(r for r in row.reasons.split(",") if r), created_at=row.created_at,
    )


def _to_reference(row: ReferenceLapRow) -> ReferenceLap:
    return ReferenceLap(id=row.id, swim_id=row.swim_id, lap_no=row.lap_no,
                        elapsed_ms=row.elapsed_ms, is_valid=row.is_valid, source=row.source)


# -- repositories -----------------------------------------------------------
class SqlUserRepository:
    def __init__(self, session: Session):
        self._s = session

    def get_by_username(self, username: str) -> User | None:
        row = self._s.scalar(select(UserRow).where(UserRow.username == username))
        return _to_user(row) if row else None

    def get_by_id(self, user_id: int) -> User | None:
        row = self._s.get(UserRow, user_id)
        return _to_user(row) if row else None

    def add(self, user: User) -> User:
        row = UserRow(username=user.username, display_name=user.display_name,
                      role=user.role.value, hashed_password=user.hashed_password,
                      is_active=user.is_active, tokens_valid_from=user.tokens_valid_from)
        self._s.add(row)
        self._s.flush()
        return _to_user(row)

    def update(self, user: User) -> User:
        row = self._s.get(UserRow, user.id)
        row.display_name = user.display_name
        row.hashed_password = user.hashed_password
        row.is_active = user.is_active
        row.tokens_valid_from = user.tokens_valid_from
        self._s.flush()
        return _to_user(row)

    def list_all(self) -> list[User]:
        return [_to_user(r) for r in self._s.scalars(select(UserRow).order_by(UserRow.id))]


class SqlVenueRepository:
    def __init__(self, session: Session):
        self._s = session

    def get(self, venue_id: int) -> Venue | None:
        row = self._s.get(VenueRow, venue_id)
        return _to_venue(row) if row else None

    def add(self, venue: Venue) -> Venue:
        row = VenueRow(name=venue.name, lane_count=venue.lane_count)
        self._s.add(row)
        self._s.flush()
        return _to_venue(row)

    def list_all(self) -> list[Venue]:
        return [_to_venue(r) for r in self._s.scalars(select(VenueRow).order_by(VenueRow.id))]


class SqlSwimmerRepository:
    def __init__(self, session: Session):
        self._s = session

    def get(self, swimmer_id: int) -> Swimmer | None:
        row = self._s.get(SwimmerRow, swimmer_id)
        return _to_swimmer(row) if row else None

    def add(self, swimmer: Swimmer) -> Swimmer:
        row = SwimmerRow(name=swimmer.name)
        self._s.add(row)
        self._s.flush()
        return _to_swimmer(row)

    def list_all(self) -> list[Swimmer]:
        return [_to_swimmer(r) for r in self._s.scalars(select(SwimmerRow).order_by(SwimmerRow.id))]


class SqlSwimRepository:
    def __init__(self, session: Session):
        self._s = session

    def get(self, swim_id: int) -> Swim | None:
        row = self._s.get(SwimRow, swim_id)
        return _to_swim(row) if row else None

    def add(self, swim: Swim) -> Swim:
        row = SwimRow(venue_id=swim.venue_id, swimmer_id=swim.swimmer_id, lane_no=swim.lane_no,
                      scheduled_start=swim.scheduled_start, lap_target=swim.lap_target,
                      status=swim.status.value)
        self._s.add(row)
        self._s.flush()
        return _to_swim(row)

    def update(self, swim: Swim) -> Swim:
        row = self._s.get(SwimRow, swim.id)
        row.lane_no = swim.lane_no
        row.scheduled_start = swim.scheduled_start
        row.lap_target = swim.lap_target
        row.status = swim.status.value
        row.closed_at = swim.closed_at
        row.closure_method = swim.closure_method.value if swim.closure_method else None
        self._s.flush()
        return _to_swim(row)

    def list_all(self) -> list[Swim]:
        return [_to_swim(r) for r in self._s.scalars(select(SwimRow).order_by(SwimRow.scheduled_start))]

    def list_by_status(self, status: SwimStatus) -> list[Swim]:
        return [_to_swim(r) for r in self._s.scalars(select(SwimRow).where(SwimRow.status == status.value))]


class SqlAssignmentRepository:
    def __init__(self, session: Session):
        self._s = session

    def add(self, assignment: Assignment) -> Assignment:
        row = AssignmentRow(swim_id=assignment.swim_id, timer_id=assignment.timer_id)
        self._s.add(row)
        self._s.flush()
        return _to_assignment(row)

    def delete(self, assignment_id: int) -> None:
        row = self._s.get(AssignmentRow, assignment_id)
        if row is not None:
            self._s.delete(row)
            self._s.flush()

    def get(self, assignment_id: int) -> Assignment | None:
        row = self._s.get(AssignmentRow, assignment_id)
        return _to_assignment(row) if row else None

    def get_for_swim(self, swim_id: int) -> Assignment | None:
        row = self._s.scalar(select(AssignmentRow).where(AssignmentRow.swim_id == swim_id))
        return _to_assignment(row) if row else None

    def list_for_timer(self, timer_id: int) -> list[Assignment]:
        return [_to_assignment(r) for r in self._s.scalars(
            select(AssignmentRow).where(AssignmentRow.timer_id == timer_id))]

    def exists(self, swim_id: int, timer_id: int) -> bool:
        return self._s.scalar(
            select(AssignmentRow.id).where(
                AssignmentRow.swim_id == swim_id, AssignmentRow.timer_id == timer_id)) is not None


class SqlLapRepository:
    def __init__(self, session: Session):
        self._s = session

    def add(self, lap: Lap) -> Lap:
        row = LapRow(
            swim_id=lap.swim_id, timer_id=lap.timer_id, seq=lap.seq,
            device_mono_ms=lap.device_mono_ms, server_ts=lap.server_ts, device_ts=lap.device_ts,
            was_buffered=lap.was_buffered, was_late=lap.was_late, is_valid=lap.is_valid,
            source=lap.source.value, reasons=",".join(lap.reasons), created_at=lap.created_at,
        )
        self._s.add(row)
        self._s.flush()
        return _to_lap(row)

    def get_by_timer_swim_seq(self, timer_id: int, swim_id: int, seq: int) -> Lap | None:
        row = self._s.scalar(select(LapRow).where(
            LapRow.timer_id == timer_id, LapRow.swim_id == swim_id, LapRow.seq == seq))
        return _to_lap(row) if row else None

    def list_for_swim(self, swim_id: int) -> list[Lap]:
        return [_to_lap(r) for r in self._s.scalars(
            select(LapRow).where(LapRow.swim_id == swim_id).order_by(LapRow.seq))]

    def highest_seq_for_swim(self, swim_id: int) -> int | None:
        return self._s.scalar(select(func.max(LapRow.seq)).where(LapRow.swim_id == swim_id))

    def last_valid_for_swim(self, swim_id: int) -> Lap | None:
        row = self._s.scalar(
            select(LapRow).where(LapRow.swim_id == swim_id, LapRow.is_valid.is_(True))
            .order_by(LapRow.seq.desc()).limit(1))
        return _to_lap(row) if row else None


class SqlReferenceLapRepository:
    def __init__(self, session: Session):
        self._s = session

    def get(self, swim_id: int, lap_no: int) -> ReferenceLap | None:
        row = self._s.scalar(select(ReferenceLapRow).where(
            ReferenceLapRow.swim_id == swim_id, ReferenceLapRow.lap_no == lap_no))
        return _to_reference(row) if row else None

    def upsert(self, ref: ReferenceLap) -> ReferenceLap:
        row = self._s.scalar(select(ReferenceLapRow).where(
            ReferenceLapRow.swim_id == ref.swim_id, ReferenceLapRow.lap_no == ref.lap_no))
        if row is None:
            row = ReferenceLapRow(swim_id=ref.swim_id, lap_no=ref.lap_no, elapsed_ms=ref.elapsed_ms,
                                  is_valid=ref.is_valid, source=ref.source)
            self._s.add(row)
        else:
            row.elapsed_ms = ref.elapsed_ms
            row.is_valid = ref.is_valid
            row.source = ref.source
        self._s.flush()
        return _to_reference(row)

    def list_for_swim(self, swim_id: int) -> list[ReferenceLap]:
        return [_to_reference(r) for r in self._s.scalars(
            select(ReferenceLapRow).where(ReferenceLapRow.swim_id == swim_id).order_by(ReferenceLapRow.lap_no))]
